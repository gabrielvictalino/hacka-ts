import asyncio
import hashlib
import shutil
import threading
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app import main
from app.config import DemoAccount, get_settings
from app.contracts import APIError
from app.db import get_engine, get_migration_config
from app.ingestion import enqueue
from app.worker import process_one
from conftest import make_pdf
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text


@pytest.fixture
def management_client(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_demo_enabled", True)
    monkeypatch.setattr(get_settings(), "auth_demo_sso_secret", SecretStr("s" * 32))
    monkeypatch.setattr(get_settings(), "auth_cookie_secure", False)
    monkeypatch.setattr(
        get_settings(), "auth_demo_users", {"curator": DemoAccount(name="Gestão", groups=["clause-gestao-acervo"])}
    )
    with TestClient(main.app) as client:
        assert client.post("/api/auth/demo/session", json={"user_id": "curator"}).status_code == 200
        yield client


def queue(topic, content):
    with get_engine().begin() as connection:
        return enqueue(connection, topic, "arquivo.pdf", content)


def test_upload_keeps_api_responsive_while_ingestion_waits(management_client, monkeypatch, topic):
    started, release = threading.Event(), threading.Event()
    observed_threads = []
    engine, original_enqueue = get_engine(), main.enqueue

    def observed_engine():
        observed_threads.append(threading.get_ident())
        return engine

    def waiting_enqueue(*args):
        observed_threads.append(threading.get_ident())
        started.set()
        if not release.wait(5):
            raise TimeoutError("O upload bloqueou o atendimento das demais rotas.")
        return original_enqueue(*args)

    monkeypatch.setattr(main, "get_engine", observed_engine)
    monkeypatch.setattr(main, "enqueue", waiting_enqueue)

    async def scenario():
        loop_thread = threading.get_ident()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="http://testserver",
            cookies=management_client.cookies,
        ) as client:
            upload = asyncio.create_task(
                client.post(
                    "/api/documents",
                    data={"topic_id": str(topic)},
                    files={"file": ("test.pdf", make_pdf(["Upload concorrente."]))},
                )
            )
            try:
                assert await asyncio.to_thread(started.wait, 2)
                assert not upload.done()
                assert len(observed_threads) == 2
                assert observed_threads[0] == observed_threads[1] != loop_thread
                for path in ("/health/live", "/health/ready", "/api/auth/me"):
                    assert (await asyncio.wait_for(client.get(path), 1)).status_code == 200
                assert not upload.done()
            finally:
                release.set()
                result = await upload
            assert result.status_code == 202

    asyncio.run(scenario())


@pytest.mark.parametrize("stored_content", [None, b"%PDF-"])
def test_missing_or_corrupt_original_is_restored_before_retry(topic, stored_content):
    content = make_pdf([f"Original recuperavel {topic}."])
    initial = queue(topic, content)
    path = get_settings().storage_path / f"{hashlib.sha256(content).hexdigest()}.pdf"
    if stored_content is None:
        path.unlink()
    else:
        path.write_bytes(stored_content)
    assert process_one()
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM document_versions WHERE id=:id"), {"id": initial.version_id}
            ).scalar_one()
            == "failed"
        )
    retry = queue(topic, content)
    assert retry.version_id == initial.version_id
    assert retry.duplicate and retry.status == "queued"
    assert path.read_bytes() == content
    assert process_one()
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM document_versions WHERE id=:id"), {"id": initial.version_id}
            ).scalar_one()
            == "ready"
        )


@pytest.mark.parametrize("stored_content", [None, b"%PDF-"])
def test_ready_version_restores_original_without_replacing_citations(topic, management_client, stored_content):
    content = make_pdf([f"Preservar citacoes {topic}."])
    initial = queue(topic, content)
    assert process_one()
    with get_engine().connect() as connection:
        passages = (
            connection.execute(
                text("""
            SELECT s.id FROM passages s JOIN pages p ON p.id=s.page_id WHERE p.version_id=:id
        """),
                {"id": initial.version_id},
            )
            .scalars()
            .all()
        )
    path = get_settings().storage_path / f"{hashlib.sha256(content).hexdigest()}.pdf"
    if stored_content is None:
        path.unlink()
    else:
        path.write_bytes(stored_content)
    response = management_client.post(
        "/api/documents", data={"topic_id": str(topic)}, files={"file": ("reenvio.pdf", content)}
    )
    assert response.status_code == 202
    assert response.json()["version_id"] == str(initial.version_id)
    assert response.json()["status"] == "ready"
    assert response.json()["duplicate"] is True
    assert management_client.get(f"/api/documents/{initial.version_id}/file").content == content
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("""
            SELECT s.id FROM passages s JOIN pages p ON p.id=s.page_id WHERE p.version_id=:id
        """),
                {"id": initial.version_id},
            )
            .scalars()
            .all()
            == passages
        )


@pytest.mark.parametrize("corruption", ["truncated", "same_size"])
def test_new_topic_repairs_corrupt_shared_original(topic, corruption):
    content = make_pdf([f"Original compartilhado {topic}."])
    initial = queue(topic, content)
    assert process_one()
    path = get_settings().storage_path / f"{hashlib.sha256(content).hexdigest()}.pdf"
    path.write_bytes(content[:10] if corruption == "truncated" else content[:-1] + b"x")
    new_topic = uuid4()
    with get_engine().begin() as connection:
        connection.execute(
            text("INSERT INTO topics(id, name) VALUES (:id, :name)"),
            {"id": new_topic, "name": f"test-{new_topic}"},
        )
    try:
        result = queue(new_topic, content)
        assert result.version_id != initial.version_id
        assert result.status == "queued" and not result.duplicate
        assert path.read_bytes() == content
        assert process_one()
        with get_engine().connect() as connection:
            assert (
                connection.execute(
                    text("SELECT status FROM document_versions WHERE id=:id"), {"id": result.version_id}
                ).scalar_one()
                == "ready"
            )
    finally:
        with get_engine().begin() as connection:
            connection.execute(text("DELETE FROM document_versions WHERE topic_id=:id"), {"id": new_topic})
            connection.execute(text("DELETE FROM documents WHERE topic_id=:id"), {"id": new_topic})
            connection.execute(text("DELETE FROM topics WHERE id=:id"), {"id": new_topic})


@pytest.mark.parametrize("stored_content", [None, b"%PDF-"])
def test_restore_failure_does_not_requeue_version(topic, monkeypatch, stored_content):
    from app import ingestion

    content = make_pdf([f"Falha de armazenamento {topic}."])
    result = queue(topic, content)
    path = get_settings().storage_path / f"{hashlib.sha256(content).hexdigest()}.pdf"
    if stored_content is None:
        path.unlink()
    else:
        path.write_bytes(stored_content)
    assert process_one()

    def fail(*args):
        raise OSError("Armazenamento indisponivel")

    monkeypatch.setattr(ingestion, "_store_original", fail)
    with pytest.raises(OSError):
        queue(topic, content)
    with get_engine().connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM document_versions WHERE id=:id"), {"id": result.version_id}
            ).scalar_one()
            == "failed"
        )


@pytest.mark.parametrize("head_count", [1, 2])
def test_readiness_tracks_alembic_heads(management_client, monkeypatch, tmp_path, head_count):
    original_config = get_migration_config()
    baseline_heads = ScriptDirectory.from_config(original_config).get_heads()
    heads = [f"test_review_{index}" for index in range(head_count)]
    original = Path(original_config.get_main_option("script_location"))
    migrations = tmp_path / "migrations"
    shutil.copytree(original, migrations)
    for head in heads:
        (migrations / "versions" / f"{head}.py").write_text(
            f"revision = {head!r}\ndown_revision = {tuple(baseline_heads)!r}\n"
            "branch_labels = None\ndepends_on = None\n"
            "def upgrade(): pass\ndef downgrade(): pass\n"
        )
    config = Config()
    config.set_main_option("script_location", str(migrations))
    monkeypatch.setattr(main, "get_migration_config", lambda: config)
    assert management_client.get("/health/ready").status_code == 503
    try:
        command.upgrade(config, "heads")
        response = management_client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["migrations"] == sorted(heads)
    finally:
        # As revisões temporárias são no-op; restaura somente o registro dos heads reais.
        command.stamp(config, baseline_heads, purge=True)


@pytest.mark.parametrize("perspective", ["deadline", "value", "obligation", "risk"])
def test_query_accepts_perspective_and_area(management_client, perspective):
    response = management_client.post(
        "/api/questions",
        json={
            "topic_id": str(uuid4()),
            "question": "Qual o prazo?",
            "perspective": perspective,
            "filters": {"area": "GGC"},
        },
    )
    assert response.status_code == 501


def test_upload_errors_and_pdf_download_match_openapi(management_client, topic):
    invalid_pdf = management_client.post(
        "/api/documents", data={"topic_id": str(topic)}, files={"file": ("invalid.pdf", b"invalid")}
    )
    invalid_fields = management_client.post("/api/documents", data={"topic_id": "invalid-uuid"})
    for response in (invalid_pdf, invalid_fields):
        assert response.status_code == 422
        APIError.model_validate(response.json())
    assert isinstance(invalid_pdf.json()["detail"], str)
    assert isinstance(invalid_fields.json()["detail"], list)
    spec = management_client.get("/openapi.json").json()
    assert spec["paths"]["/api/documents"]["post"]["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/APIError",
    }
    pdf_response = spec["paths"]["/api/documents/{version_id}/file"]["get"]["responses"]["200"]
    assert pdf_response["content"] == {
        "application/pdf": {"schema": {"type": "string", "format": "binary"}},
    }
