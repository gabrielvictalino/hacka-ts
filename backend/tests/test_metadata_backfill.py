import hashlib
from uuid import uuid4

import pytest
from alembic import command
from app.db import get_engine, get_migration_config
from app.ingestion import backfill_metadata, enqueue, extract_pages
from conftest import make_pdf
from sqlalchemy import text

HEADER = """Documento: Norma Geral
Título: Férias
Sigla e Número: NG_111 Versão: {version}
Fase: {phase} Vigência: 03/08/2026 a 03/02/2028
Vinculado a: PX_1111-001
DOCUMENTO SINTÉTICO.
4.3.1. Solicitação com antecedência mínima de 45 dias corridos.
"""


def seed_legacy(topic, version, title="Férias", suffix=""):
    content = make_pdf(
        [HEADER.format(version=version, phase="Vigente").replace("Título: Férias", f"Título: {title}") + suffix]
    )
    page_text = extract_pages(content)[0]
    document_id, version_id, page_id, passage_id = (uuid4() for _ in range(4))
    digest = hashlib.sha256(content).hexdigest()
    with get_engine().begin() as connection:
        connection.execute(
            text("INSERT INTO documents(id, topic_id, title) VALUES (:id, :topic, 'arquivo.pdf')"),
            {"id": document_id, "topic": topic},
        )
        connection.execute(
            text("""INSERT INTO document_versions
            (id, document_id, topic_id, filename, storage_key, sha256, status, page_count, processed_at)
            VALUES (:id, :document, :topic, 'arquivo.pdf', :key, :sha, 'ready', 1, now())"""),
            {"id": version_id, "document": document_id, "topic": topic, "key": f"{digest}.pdf", "sha": digest},
        )
        connection.execute(
            text("INSERT INTO pages(id, version_id, physical_page, text) VALUES (:id, :version, 1, :text)"),
            {"id": page_id, "version": version_id, "text": page_text},
        )
        # Simula o recorte da fundação, sem recriar o trecho nem atribuir uma seção na atualização.
        connection.execute(
            text("INSERT INTO passages(id, page_id, ordinal, excerpt) VALUES (:id, :page, 0, :excerpt)"),
            {"id": passage_id, "page": page_id, "excerpt": page_text[:1500]},
        )
    return {"id": version_id, "page_id": page_id, "passage_id": passage_id, "content": content, "text": page_text}


def assert_preserved_and_enriched(topic, versions):
    with get_engine().connect() as connection:
        rows = (
            connection.execute(
                text("""SELECT v.id, v.document_id, v.title, v.version, v.document_type,
            v.declared_phase, v.linked_codes, v.status, v.processed_pages, p.id AS page_id, p.text,
            s.id AS passage_id, s.excerpt, s.section, d.code FROM document_versions v
            JOIN documents d ON d.id=v.document_id JOIN pages p ON p.version_id=v.id
            JOIN passages s ON s.page_id=p.id WHERE v.topic_id=:topic"""),
                {"topic": topic},
            )
            .mappings()
            .all()
        )
        assert len(rows) == len(versions)
        assert len({row["document_id"] for row in rows}) == 1
        for legacy in versions:
            row = next(row for row in rows if row["id"] == legacy["id"])
            assert row["page_id"] == legacy["page_id"] and row["passage_id"] == legacy["passage_id"]
            assert row["text"] == legacy["text"] and row["excerpt"] == legacy["text"][:1500]
            assert row["section"] is None
            assert row["code"] == "NG_111" and row["version"] in {"2.0.0", "3.0.0"}
            assert row["title"] in {"Férias", "Novas férias"}
            assert row["document_type"] == "Norma Geral" and row["declared_phase"] == "Vigente"
            assert row["linked_codes"] == ["PX_1111-001"] and row["status"] == "ready"
            assert row["processed_pages"] == 1
        assert (
            connection.execute(text("SELECT count(*) FROM documents WHERE topic_id=:topic"), {"topic": topic}).scalar()
            == 1
        )


def test_migration_enriches_legacy_editions_and_preserves_curated_citations(topic):
    config = get_migration_config()
    fact_id = uuid4()
    try:
        command.downgrade(config, "0001")
        versions = [seed_legacy(topic, "2.0.0"), seed_legacy(topic, "3.0.0", "Novas férias")]
        with get_engine().begin() as connection:
            connection.execute(
                text("""INSERT INTO curated_facts(id, topic_id, category, statement, curated_by)
                VALUES (:id, :topic, 'deadline', 'Prazo revisado', 'Gestão')"""),
                {"id": fact_id, "topic": topic},
            )
            connection.execute(
                text("INSERT INTO fact_citations(fact_id, passage_id) VALUES (:fact, :passage)"),
                {"fact": fact_id, "passage": versions[0]["passage_id"]},
            )
        command.upgrade(config, "heads")
        assert_preserved_and_enriched(topic, versions)
        # A repetição não altera as fontes publicadas, mesmo sem originais no disco.
        with get_engine().begin() as connection:
            backfill_metadata(connection)
            assert (
                connection.execute(
                    text("SELECT passage_id FROM fact_citations WHERE fact_id=:id"), {"id": fact_id}
                ).scalar_one()
                == versions[0]["passage_id"]
            )
        assert_preserved_and_enriched(topic, versions)
        command.downgrade(config, "0002")
        assert_preserved_and_enriched(topic, versions)
        command.upgrade(config, "heads")
    finally:
        command.upgrade(config, "heads")
        with get_engine().begin() as connection:
            connection.execute(text("DELETE FROM curated_facts WHERE id=:id"), {"id": fact_id})


def test_reimport_enriches_ready_legacy_version_without_replacing_citations(topic):
    legacy = seed_legacy(topic, "3.0.0")
    for _ in range(2):
        with get_engine().begin() as connection:
            result = enqueue(connection, topic, "reenvio.pdf", legacy["content"])
        assert result.version_id == legacy["id"] and result.status == "ready" and result.duplicate
        assert_preserved_and_enriched(topic, [legacy])


def test_backfill_failure_rolls_back_metadata_and_keeps_citations(topic, monkeypatch):
    from app import ingestion

    versions = [seed_legacy(topic, "2.0.0"), seed_legacy(topic, "3.0.0")]
    original_update = ingestion.update_metadata
    called = []

    def fail_second(connection, job, page, **kwargs):
        original_update(connection, job, page, **kwargs)
        called.append(job["id"])
        if len(called) == 2:
            raise RuntimeError("Falha durante atualização")

    monkeypatch.setattr(ingestion, "update_metadata", fail_second)
    with pytest.raises(RuntimeError):
        with get_engine().begin() as connection:
            backfill_metadata(connection)
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM document_versions WHERE topic_id=:topic AND title IS NULL"), {"topic": topic}
            ).scalar()
            == 2
        )
        passages = set(
            connection.execute(
                text("""SELECT s.id FROM passages s JOIN pages p ON p.id=s.page_id
            JOIN document_versions v ON v.id=p.version_id WHERE v.topic_id=:topic"""),
                {"topic": topic},
            ).scalars()
        )
        assert passages == {version["passage_id"] for version in versions}


def test_migration_continues_on_legacy_duplicate_editions_and_preserves_all_citations(topic):
    config = get_migration_config()
    fact_id = uuid4()
    try:
        command.downgrade(config, "0001")
        first = seed_legacy(topic, "3.0.0")
        conflicting = seed_legacy(topic, "3.0.0", suffix="Outra orientação no mesmo código e versão.")
        following = seed_legacy(topic, "2.0.0", "Novas férias")
        versions = [first, conflicting, following]
        assert first["content"] != conflicting["content"]
        with get_engine().begin() as connection:
            connection.execute(
                text("""INSERT INTO curated_facts(id, topic_id, category, statement, curated_by)
                VALUES (:id, :topic, 'deadline', 'Prazo revisado', 'Gestão')"""),
                {"id": fact_id, "topic": topic},
            )
            for legacy in versions:
                connection.execute(
                    text("INSERT INTO fact_citations(fact_id, passage_id) VALUES (:fact, :passage)"),
                    {"fact": fact_id, "passage": legacy["passage_id"]},
                )
        command.upgrade(config, "heads")
        with get_engine().connect() as connection:
            rows = (
                connection.execute(
                    text("""SELECT v.id, v.status, v.error, v.title, v.version, v.sha256,
                v.storage_key, v.linked_codes, d.code, v.document_id, p.id AS page_id, p.text,
                s.id AS passage_id, s.excerpt FROM document_versions v JOIN documents d ON d.id=v.document_id
                JOIN pages p ON p.version_id=v.id JOIN passages s ON s.page_id=p.id
                WHERE v.topic_id=:topic"""),
                    {"topic": topic},
                )
                .mappings()
                .all()
            )
            assert len(rows) == 3 and len({row["document_id"] for row in rows}) == 1
            for legacy in versions:
                row = next(row for row in rows if row["id"] == legacy["id"])
                assert row["page_id"] == legacy["page_id"] and row["passage_id"] == legacy["passage_id"]
                assert row["text"] == legacy["text"] and row["excerpt"] == legacy["text"][:1500]
                assert row["sha256"] == hashlib.sha256(legacy["content"]).hexdigest()
                assert row["storage_key"] == f"{row['sha256']}.pdf"
                assert row["code"] == "NG_111" and row["linked_codes"] == ["PX_1111-001"]
                if legacy is conflicting:
                    assert row["status"] == "failed" and row["version"] == "3.0.0"
                    assert "NG_111 v3.0.0" in row["error"] and str(first["id"]) in row["error"]
                else:
                    assert row["status"] == "ready" and row["error"] is None
            assert set(
                connection.execute(
                    text("SELECT passage_id FROM fact_citations WHERE fact_id=:id"), {"id": fact_id}
                ).scalars()
            ) == {v["passage_id"] for v in versions}
            snapshot = rows
        # Repetir o backfill e o reenvio mantém o conflito e todas as fontes intactas.
        with get_engine().begin() as connection:
            backfill_metadata(connection)
            result = enqueue(connection, topic, "reenvio.pdf", conflicting["content"])
        assert result.version_id == conflicting["id"] and result.status == "failed" and result.duplicate
        assert str(first["id"]) in result.error
        with get_engine().connect() as connection:
            for row in snapshot:
                current = connection.execute(
                    text("SELECT status, error FROM document_versions WHERE id=:id"), {"id": row["id"]}
                ).one()
                assert current == (row["status"], row["error"])
            assert (
                connection.execute(
                    text("""SELECT count(*) FROM pages p JOIN document_versions v ON v.id=p.version_id
                WHERE v.topic_id=:topic"""),
                    {"topic": topic},
                ).scalar()
                == 3
            )
        from app.worker import process_one

        assert process_one() is False
    finally:
        command.upgrade(config, "heads")
        with get_engine().begin() as connection:
            connection.execute(text("DELETE FROM curated_facts WHERE id=:id"), {"id": fact_id})


def test_reimport_marks_legacy_conflict_without_recreating_sources(topic):
    first = seed_legacy(topic, "3.0.0")
    conflicting = seed_legacy(topic, "3.0.0", suffix="Conteúdo divergente.")
    with get_engine().begin() as connection:
        initial = enqueue(connection, topic, "primeiro.pdf", first["content"])
    assert initial.status == "ready"
    for _ in range(2):
        with get_engine().begin() as connection:
            result = enqueue(connection, topic, "reenvio.pdf", conflicting["content"])
        assert result.version_id == conflicting["id"] and result.status == "failed" and result.duplicate
        assert str(first["id"]) in result.error
    with get_engine().connect() as connection:
        row = connection.execute(
            text("""SELECT p.id, s.id, s.excerpt FROM pages p JOIN passages s ON s.page_id=p.id
            WHERE p.version_id=:id"""),
            {"id": conflicting["id"]},
        ).one()
        assert row == (conflicting["page_id"], conflicting["passage_id"], conflicting["text"][:1500])


def test_import_cli_returns_failure_for_legacy_conflict_and_continues(topic, tmp_path, monkeypatch, capsys):
    import json
    import sys

    from app.import_collection import main

    first = seed_legacy(topic, "3.0.0")
    conflicting = seed_legacy(topic, "3.0.0", suffix="Conteúdo conflitante para testar o CLI.")
    with get_engine().begin() as connection:
        enqueue(connection, topic, "first.pdf", first["content"])
    directory = tmp_path / f"test-{topic}"
    directory.mkdir()
    (directory / "01-valid.pdf").write_bytes(make_pdf(["Documento válido antes do conflito."]))
    (directory / "02-conflict.pdf").write_bytes(conflicting["content"])
    (directory / "03-valid.pdf").write_bytes(make_pdf(["Documento válido depois do conflito."]))
    monkeypatch.setattr(sys, "argv", ["import_collection", str(tmp_path)])
    for duplicate in (False, True):
        with pytest.raises(SystemExit) as result:
            main()
        assert result.value.code == 1
        records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        assert [record["file"] for record in records] == [
            f"test-{topic}/01-valid.pdf",
            f"test-{topic}/02-conflict.pdf",
            f"test-{topic}/03-valid.pdf",
        ]
        assert [record["status"] for record in records] == ["queued", "failed", "queued"]
        assert records[0]["duplicate"] is duplicate and records[2]["duplicate"] is duplicate
        assert records[1]["version_id"] == str(conflicting["id"]) and records[1]["duplicate"] is True
        assert str(first["id"]) in records[1]["error"]
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM document_versions WHERE topic_id=:topic"), {"topic": topic}
            ).scalar()
            == 4
        )
        assert set(
            connection.execute(
                text("""SELECT s.id FROM passages s JOIN pages p ON p.id=s.page_id
            JOIN document_versions v ON v.id=p.version_id WHERE v.topic_id=:topic"""),
                {"topic": topic},
            ).scalars()
        ) == {first["passage_id"], conflicting["passage_id"]}
