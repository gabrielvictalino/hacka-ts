from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from app.config import get_settings
from app.ingestion import InvalidDocument, enqueue, extract_pages
from app.main import app
from app.worker import process_one
from conftest import make_pdf
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.fixture
def client(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_demo_enabled", True)
    monkeypatch.setattr(
        settings,
        "auth_demo_users",
        {
            "reader": {"name": "Leitura", "role": "empregado"},
            "curator": {"name": "Gestão", "role": "gestao"},
        },
    )
    with TestClient(app) as client:
        yield client


def queue(topic, content):
    from app.db import get_engine

    with get_engine().begin() as connection:
        return enqueue(connection, topic, "arquivo.pdf", content)


def test_auth_requires_signed_session(client):
    assert client.get("/api/topics", headers={"X-Role": "gestao"}).status_code == 401
    client.cookies.set("ipbot_session", "invalid")
    assert client.get("/api/auth/me").status_code == 401


def test_reader_cannot_ingest_but_management_can(client, topic):
    assert client.post("/api/auth/demo/session", json={"user_id": "reader"}).status_code == 200
    assert client.get("/api/topics").status_code == 200
    content = make_pdf(["Prazo de 30 dias."])
    assert (
        client.post(
            "/api/documents",
            data={"topic_id": str(topic)},
            files={"file": ("test.pdf", content)},
        ).status_code
        == 403
    )
    assert client.post("/api/auth/demo/session", json={"user_id": "curator"}).status_code == 200
    response = client.post(
        "/api/documents",
        data={"topic_id": str(topic)},
        files={"file": ("test.pdf", content)},
    )
    assert response.status_code == 202
    version = response.json()["version_id"]
    assert client.get(f"/api/documents/{version}/file").content == content


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": datetime.now(timezone.utc) - timedelta(seconds=10)},
        {"iss": "outro"},
        {"aud": "outro"},
    ],
)
def test_rejects_invalid_claims(client, changes):
    claims = {
        "sub": "curator",
        "name": "Gestão",
        "role": "gestao",
        "simulated": True,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iss": "ipbot-local-demo",
        "aud": "ipbot-api",
        **changes,
    }
    token = jwt.encode(claims, get_settings().auth_secret.get_secret_value(), algorithm="HS256")
    client.cookies.set("ipbot_session", token)
    assert client.get("/api/auth/me").status_code == 401


def test_disabled_simulator(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_demo_enabled", False)
    assert client.get("/api/auth/demo/users").status_code == 404
    assert client.post("/api/auth/demo/session", json={"user_id": "curator"}).status_code == 404


def test_preserves_blank_physical_pages_and_literal_passages(topic):
    from app.db import get_engine

    result = queue(topic, make_pdf(["", "Prazo de 30 dias."]))
    assert process_one()
    with get_engine().connect() as connection:
        pages = connection.execute(
            text("SELECT physical_page, text FROM pages WHERE version_id=:id ORDER BY physical_page"),
            {"id": result.version_id},
        ).all()
        assert [page[0] for page in pages] == [1, 2]
        assert pages[0][1] == ""
        passage = connection.execute(
            text("""
            SELECT p.physical_page, s.excerpt FROM passages s JOIN pages p ON p.id=s.page_id
            JOIN document_versions v ON v.id=p.version_id WHERE v.id=:id AND v.status='ready'
        """),
            {"id": result.version_id},
        ).one()
        assert passage[0] == 2
        assert passage[1] in pages[1][1]
        assert connection.execute(text("SELECT to_regclass('ix_passages_search')")).scalar()


def test_concurrent_duplicate_is_idempotent(topic):
    content = make_pdf(["Mesmo documento."])
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: queue(topic, content), range(2)))
    assert results[0].version_id == results[1].version_id
    assert sorted(result.duplicate for result in results) == [False, True]


def test_concurrent_workers_process_each_version_once(topic):
    from app.db import get_engine

    queue(topic, make_pdf(["Primeiro documento."]))
    queue(topic, make_pdf(["Segundo documento."]))
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert all(executor.map(lambda _: process_one(), range(2)))
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM document_versions WHERE topic_id=:id AND status='ready'"),
                {"id": topic},
            ).scalar()
            == 2
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM pages p JOIN document_versions v ON v.id=p.version_id WHERE v.topic_id=:id"),
                {"id": topic},
            ).scalar()
            == 2
        )


def test_worker_skips_locked_job_and_reclaims_after_rollback(topic):
    from app.db import get_engine

    result = queue(topic, make_pdf(["Trabalho recuperavel."]))
    with get_engine().connect() as connection:
        transaction = connection.begin()
        connection.execute(
            text("SELECT id FROM document_versions WHERE id=:id FOR UPDATE"),
            {"id": result.version_id},
        )
        assert process_one() is False
        transaction.rollback()
    assert process_one() is True


@pytest.mark.parametrize("content", [b"%PDF-invalid", make_pdf([""])])
def test_failure_has_no_partial_pages_and_can_retry(topic, content):
    from app.db import get_engine

    result = queue(topic, content)
    assert process_one()
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM document_versions WHERE id=:id"),
                {"id": result.version_id},
            ).scalar()
            == "failed"
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM pages WHERE version_id=:id"),
                {"id": result.version_id},
            ).scalar()
            == 0
        )
    retry = queue(topic, content)
    assert retry.version_id == result.version_id
    assert retry.status == "queued"
    assert retry.duplicate


def test_non_pdf_is_rejected(topic):
    with pytest.raises(InvalidDocument):
        queue(topic, b"not a pdf")


def test_pdf_without_text_is_explicit():
    with pytest.raises(InvalidDocument, match="OCR"):
        extract_pages(make_pdf([""]))


def test_unsupported_text_fails_without_blocking_next_document(topic):
    from app.db import get_engine

    invalid = queue(topic, make_pdf(["Pagina valida.", "Texto com caractere nulo: \x00 fim."]))
    valid = queue(topic, make_pdf(["Documento seguinte valido."]))
    assert process_one()
    assert process_one()
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM document_versions WHERE id=:id"),
                {"id": invalid.version_id},
            ).scalar_one()
            == "failed"
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM pages WHERE version_id=:id"),
                {"id": invalid.version_id},
            ).scalar_one()
            == 0
        )
        assert (
            connection.execute(
                text("SELECT status FROM document_versions WHERE id=:id"),
                {"id": valid.version_id},
            ).scalar_one()
            == "ready"
        )


def test_import_command_uses_topic_folders_and_shared_deduplication(topic, tmp_path, monkeypatch, capsys):
    import json
    import sys

    from app.import_collection import main

    directory = tmp_path / f"test-{topic}"
    directory.mkdir()
    (directory / "norma.pdf").write_bytes(make_pdf(["Norma para importacao."]))
    (tmp_path / "catalogo.pdf").write_bytes(b"catalogo auxiliar nao deve ser importado")
    monkeypatch.setattr(sys, "argv", ["import_collection", str(tmp_path)])
    for duplicate in (False, True):
        with pytest.raises(SystemExit) as result:
            main()
        assert result.value.code == 0
        records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        assert len(records) == 1
        assert records[0]["duplicate"] is duplicate
        assert records[0]["status"] == "queued"


def test_health_and_query_contract_are_available(client):
    assert client.get("/health/ready").status_code == 200
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert {
        "Citation",
        "QuestionRequest",
        "QuestionResponse",
        "Identity",
        "IngestionResult",
    } <= schemas.keys()
    assert schemas["Citation"]["properties"]["physical_page"]["minimum"] == 1
