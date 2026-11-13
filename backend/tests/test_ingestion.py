import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4

import pytest
from app.config import DemoAccount, get_settings
from app.db import get_engine
from app.document_parser import page_passages, read_header
from app.ingestion import enqueue
from app.main import app
from app.worker import process_one
from conftest import make_pdf
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

HEADER = """Documento: Norma Geral
Título: Férias
Sigla e Número: NG_111 Versão: {version}
Elaborado por: GGC
Aprovado por: DIRAF
Fase: {phase} Vigência: 03/08/2026 a 03/02/2028
Vinculado a: PX_1111-001
DOCUMENTO SINTÉTICO.
1. Objetivo
Preservar as regras.
4.3.1. Solicitar com 45 dias de antecedência.
"""


def queue(topic, pages):
    content = make_pdf(pages)
    with get_engine().begin() as connection:
        result = enqueue(connection, topic, "norma.pdf", content)
    return result, content


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_demo_enabled", True)
    monkeypatch.setattr(get_settings(), "auth_demo_sso_secret", SecretStr("s" * 32))
    monkeypatch.setattr(get_settings(), "auth_cookie_secure", False)
    monkeypatch.setattr(
        get_settings(),
        "auth_demo_users",
        {
            "reader": DemoAccount(name="Consulta", groups=["clause-empregados"]),
            "manager": DemoAccount(name="Gestor", groups=["clause-gestores"]),
            "curator": DemoAccount(name="Gestão", groups=["clause-gestao-acervo"]),
        },
    )
    with TestClient(app) as client:
        assert client.post("/api/auth/demo/session", json={"user_id": "curator"}).status_code == 200
        yield client


def test_header_preserves_declared_phase_dates_and_explicit_links():
    metadata = read_header(HEADER.format(version="3.0.0", phase="Versão anterior"))
    assert metadata == {
        "title": "Férias",
        "code": "NG_111",
        "version": "3.0.0",
        "document_type": "Norma Geral",
        "document_layer": "norma geral",
        "declared_phase": "Versão anterior",
        "valid_from": date(2026, 8, 3),
        "valid_until": date(2028, 2, 3),
        "linked_codes": ["PX_1111-001"],
    }
    note = read_header(
        "Documento: Nota Técnica\nSigla e Número: NT_2026-018 Versão: 1.0.0\n"
        "Referência: CTR_2026-012\nFase: Vigente Assinada em: 05/11/2026\nDOCUMENTO SINTÉTICO."
    )
    assert note["linked_codes"] == ["CTR_2026-012"]
    assert note["valid_from"] is None
    assert note["declared_phase"] == "Vigente"
    assert read_header("Sem cabeçalho, menciona NG_111 no texto.")["code"] is None


def test_passages_keep_complete_long_items_and_clause_continuations():
    long_item = ("4.3.1. " + "Texto literal com condições. " * 150).rstrip()
    page = "Cabeçalho\n" + long_item + "\n4.3.2. Próximo item."
    passages = list(page_passages(page))
    assert passages == [(None, "Cabeçalho"), ("4.3.1", long_item), ("4.3.2", "4.3.2. Próximo item.")]
    clauses = list(page_passages("CLÁUSULA PRIMEIRA — Objeto.\nContinua aqui.\nCLÁUSULA SEGUNDA — Prazo."))
    assert clauses[0][0] == "CLÁUSULA PRIMEIRA"
    assert list(page_passages("continuação na página seguinte", clauses[-1][0]))[0][0] == "CLÁUSULA SEGUNDA"
    for _, excerpt in passages:
        assert excerpt in page


def test_versions_share_document_identity_preserve_titles_and_citation_ids(topic, client):
    first, content = queue(topic, [HEADER.format(version="2.0.0", phase="Versão anterior")])
    second, _ = queue(
        topic, [HEADER.format(version="3.0.0", phase="Vigente").replace("Título: Férias", "Título: Novas férias")]
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert all(executor.map(lambda _: process_one(), range(2)))
    rows = client.get("/api/documents", params={"topic_id": str(topic)}).json()
    assert len({row["document_id"] for row in rows}) == 1
    assert {row["title"] for row in rows} == {"Férias", "Novas férias"}
    assert {row["version"] for row in rows} == {"2.0.0", "3.0.0"}
    assert all(row["status"] == "ready" and row["processed_pages"] == 1 for row in rows)
    assert all(row["linked_codes"] == ["PX_1111-001"] for row in rows)
    with get_engine().connect() as connection:
        citations = connection.execute(
            text("""SELECT s.id, s.section, s.excerpt, p.text FROM passages s
            JOIN pages p ON p.id=s.page_id WHERE p.version_id=:id ORDER BY s.ordinal"""),
            {"id": first.version_id},
        ).all()
    assert any(row.section == "4.3.1" for row in citations)
    assert all(row.excerpt in row.text for row in citations)
    response = client.post("/api/documents", data={"topic_id": str(topic)}, files={"file": ("same.pdf", content)})
    assert response.json()["version_id"] == str(first.version_id)
    with get_engine().connect() as connection:
        assert set(
            connection.execute(
                text("""SELECT s.id FROM passages s JOIN pages p ON p.id=s.page_id
            WHERE p.version_id=:id"""),
                {"id": first.version_id},
            ).scalars()
        ) == {row.id for row in citations}
        assert (
            connection.execute(text("SELECT count(*) FROM curated_facts WHERE topic_id=:id"), {"id": topic}).scalar()
            == 0
        )
    assert second.version_id != first.version_id


def test_rejects_conflicting_edition_without_publishing_partial_pages(topic):
    first, _ = queue(topic, [HEADER.format(version="3.0.0", phase="Vigente")])
    second, _ = queue(topic, [HEADER.format(version="3.0.0", phase="Vigente") + "Conteúdo alterado."])
    assert process_one() and process_one()
    with get_engine().connect() as connection:
        rows = dict(
            connection.execute(text("SELECT id, status FROM document_versions WHERE topic_id=:id"), {"id": topic}).all()
        )
        assert rows == {first.version_id: "ready", second.version_id: "failed"}
        assert (
            connection.execute(
                text("SELECT count(*) FROM pages WHERE version_id=:id"), {"id": second.version_id}
            ).scalar()
            == 0
        )


def test_processing_is_visible_and_recovers_after_worker_crash(topic, monkeypatch, client):
    from app import worker

    result, _ = queue(topic, ["Página um.", "Página dois."])
    original_progress = worker._progress
    observed = []

    def progress(identifier, **values):
        original_progress(identifier, **values)
        row = client.get("/api/documents", params={"topic_id": str(topic)}).json()[0]
        observed.append(row)
        if values["processed_pages"] == 1:
            raise RuntimeError("Simula queda do worker")

    monkeypatch.setattr(worker, "_progress", progress)
    with pytest.raises(RuntimeError, match="queda"):
        process_one()
    assert all(row["status"] == "processing" for row in observed)
    assert observed[-1]["processed_pages"] == 1
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM pages WHERE version_id=:id"), {"id": result.version_id}
            ).scalar()
            == 0
        )
    monkeypatch.setattr(worker, "_progress", original_progress)
    assert process_one()
    row = client.get("/api/documents", params={"topic_id": str(topic)}).json()[0]
    assert row["status"] == "ready" and row["page_count"] == 2


def test_batch_isolates_rejections_and_retry_requires_management(topic, client):
    data = {"topic_id": str(topic)}
    files = [("files", ("ok.pdf", make_pdf(["Documento válido."]))), ("files", ("bad.pdf", b"invalid"))]
    response = client.post("/api/documents/batch", data=data, files=files)
    assert response.status_code == 202
    accepted, rejected = response.json()
    assert accepted["result"]["status"] == "queued"
    assert rejected["error"] and rejected["result"] is None
    invalid, _ = queue(topic, [""])
    assert process_one() and process_one()
    assert client.post(f"/api/documents/{invalid.version_id}/retry").json()["status"] == "queued"
    assert client.post("/api/auth/demo/session", json={"user_id": "reader"}).status_code == 200
    assert client.post("/api/documents/batch", data=data, files=files).status_code == 403
    assert client.post(f"/api/documents/{invalid.version_id}/retry").status_code == 403
    assert client.post("/api/topics", json={"name": "Proibido"}).status_code == 403
    assert client.get("/api/documents", params={"topic_id": str(topic)}).status_code == 200


def test_retry_corrupt_original_does_not_create_another_version(topic, client):
    result, _ = queue(topic, ["Original."])
    with get_engine().connect() as connection:
        key = connection.execute(
            text("SELECT storage_key FROM document_versions WHERE id=:id"), {"id": result.version_id}
        ).scalar_one()
    (get_settings().storage_path / key).write_bytes(make_pdf(["Alterado."]))
    assert client.post(f"/api/documents/{result.version_id}/retry").status_code == 422
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM document_versions WHERE topic_id=:id"), {"id": topic}
            ).scalar()
            == 1
        )


def test_create_topic_trims_name_and_is_idempotent(topic, client):
    with get_engine().connect() as connection:
        name = connection.execute(text("SELECT name FROM topics WHERE id=:id"), {"id": topic}).scalar_one()
    assert client.post("/api/topics", json={"name": f" {name} "}).json()["id"] == str(topic)
    assert client.post("/api/topics", json={"name": "   "}).status_code == 422
    assert client.post(f"/api/documents/{uuid4()}/retry").status_code == 404


def test_batch_database_failure_keeps_committed_files_and_continues(topic, client, monkeypatch):
    from app import main

    original_enqueue = main.enqueue
    attempted = []

    def fail_middle(connection, topic_id, filename, content):
        attempted.append(filename)
        result = original_enqueue(connection, topic_id, filename, content)
        if filename == "middle.pdf":
            raise SQLAlchemyError("Mensagem interna do banco não deve aparecer na resposta")
        return result

    monkeypatch.setattr(main, "enqueue", fail_middle)
    response = client.post(
        "/api/documents/batch",
        data={"topic_id": str(topic)},
        files=[("files", (name, make_pdf([name]))) for name in ("first.pdf", "middle.pdf", "last.pdf")],
    )
    assert response.status_code == 202
    first, middle, last = response.json()
    assert attempted == ["first.pdf", "middle.pdf", "last.pdf"]
    assert first["result"]["status"] == last["result"]["status"] == "queued"
    assert first["error"] is last["error"] is None
    assert middle["result"] is None and "Banco indisponível" in middle["error"]
    assert "Mensagem interna" not in response.text
    with get_engine().connect() as connection:
        filenames = (
            connection.execute(
                text("SELECT filename FROM document_versions WHERE topic_id=:id ORDER BY filename"),
                {"id": topic},
            )
            .scalars()
            .all()
        )
    assert filenames == ["first.pdf", "last.pdf"]


@pytest.mark.parametrize("subject, expected", [(None, 401), ("reader", 403), ("manager", 403), ("curator", 202)])
def test_ingestion_routes_use_current_sso_permissions(topic, client, subject, expected):
    result, content = queue(topic, ["Documento para verificar autorização."])
    client.cookies.clear()
    if subject:
        assert client.post("/api/auth/demo/session", json={"user_id": subject}).status_code == 200
    assert (
        client.post(
            "/api/documents",
            data={"topic_id": str(topic)},
            files={"file": ("norma.pdf", content)},
        ).status_code
        == expected
    )
    assert (
        client.post(
            "/api/documents/batch",
            data={"topic_id": str(topic)},
            files={"files": ("norma.pdf", content)},
        ).status_code
        == expected
    )
    assert client.post(f"/api/documents/{result.version_id}/retry").status_code == expected
    with get_engine().connect() as connection:
        name = connection.execute(text("SELECT name FROM topics WHERE id=:id"), {"id": topic}).scalar_one()
    assert client.post("/api/topics", json={"name": name}).status_code == (200 if expected == 202 else expected)


def test_legacy_conflict_is_visible_and_retry_preserves_citations(topic, client):
    from app.ingestion import backfill_metadata
    from test_metadata_backfill import seed_legacy

    first = seed_legacy(topic, "3.0.0")
    conflicting = seed_legacy(topic, "3.0.0", suffix="Conteúdo divergente.")
    original_path = get_settings().storage_path / f"{hashlib.sha256(conflicting['content']).hexdigest()}.pdf"
    original_path.write_bytes(conflicting["content"])
    with get_engine().begin() as connection:
        backfill_metadata(connection)
    rows = client.get("/api/documents", params={"topic_id": str(topic)}).json()
    conflict = next(row for row in rows if row["id"] == str(conflicting["id"]))
    assert conflict["status"] == "failed" and str(first["id"]) in conflict["error"]
    assert conflict["code"] == "NG_111" and conflict["version"] == "3.0.0"
    assert client.get(f"/api/documents/{conflicting['id']}/file").content == conflicting["content"]
    # O reenvio conserva o original e as citações, sem permitir nova extração.
    response = client.post(
        "/api/documents", data={"topic_id": str(topic)}, files={"file": ("reenvio.pdf", conflicting["content"])}
    )
    assert response.status_code == 202 and response.json()["status"] == "failed"
    assert client.get(f"/api/documents/{conflicting['id']}/file").content == conflicting["content"]
    retry = client.post(f"/api/documents/{conflicting['id']}/retry")
    assert retry.status_code == 202 and retry.json()["status"] == "failed" and retry.json()["duplicate"]
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("""SELECT s.id FROM passages s JOIN pages p ON p.id=s.page_id
            WHERE p.version_id=:id"""),
                {"id": conflicting["id"]},
            ).scalar_one()
            == conflicting["passage_id"]
        )


def test_new_upload_cannot_replace_conflicting_legacy_source(topic):
    from app.ingestion import backfill_metadata
    from test_metadata_backfill import seed_legacy

    first = seed_legacy(topic, "3.0.0")
    conflicting = seed_legacy(topic, "3.0.0", suffix="Conteúdo divergente.")
    with get_engine().begin() as connection:
        backfill_metadata(connection)
        # Mesmo se a outra fonte deixar de estar pronta, a fonte citada em conflito continua protegida.
        connection.execute(text("UPDATE document_versions SET status='failed' WHERE id=:id"), {"id": first["id"]})
    new, _ = queue(topic, [HEADER.format(version="3.0.0", phase="Vigente") + "Terceiro conteúdo."])
    assert process_one()
    with get_engine().connect() as connection:
        row = connection.execute(
            text("SELECT status, error FROM document_versions WHERE id=:id"), {"id": new.version_id}
        ).one()
        assert row.status == "failed" and "Código e versão já publicados" in row.error
        assert (
            connection.execute(
                text("SELECT id FROM passages WHERE id=:id"), {"id": conflicting["passage_id"]}
            ).scalar_one()
            == conflicting["passage_id"]
        )
