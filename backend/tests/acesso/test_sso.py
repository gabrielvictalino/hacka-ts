from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from app import main
from app.auth import ASSERTION_AUDIENCE, ASSERTION_ISSUER
from app.config import DemoAccount, get_settings
from app.main import app
from conftest import make_pdf
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Uuid, bindparam, create_engine, text


@pytest.fixture
def client(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_demo_enabled", True)
    monkeypatch.setattr(settings, "auth_demo_sso_secret", SecretStr("s" * 32))
    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    monkeypatch.setattr(
        settings,
        "auth_demo_users",
        {
            "a": DemoAccount(name="Empregado", groups=["clause-empregados"]),
            "b": DemoAccount(name="Gestor", groups=["clause-gestores"]),
            "c": DemoAccount(name="Gestão", groups=["clause-empregados", "clause-gestao-acervo"]),
        },
    )
    with TestClient(app, base_url="https://testserver") as client:
        yield client


def assertion(client, user_id="a"):
    response = client.post("/api/auth/demo/assertion", json={"user_id": user_id})
    assert response.status_code == 200
    return response.json()["token"]


@pytest.mark.parametrize(
    ("account", "role", "alerts_status"), [("a", "empregado", 403), ("b", "gestor", 403), ("c", "gestao", 501)]
)
def test_group_controls_session_and_alerts(client, account, role, alerts_status):
    assert len(client.get("/api/auth/demo/users").json()) == 3
    token = assertion(client, account)
    assert not client.cookies
    result = client.post("/auth/callback", json={"token": token}, headers={"X-Role": "gestao"})
    assert result.status_code == 200
    assert result.json()["role"] == role
    assert result.json()["simulated"] is True
    expected_permissions = {"documents:read"}
    if role == "gestao":
        expected_permissions.update({"documents:ingest", "facts:curate", "alerts:read-details"})
    else:
        assert client.post("/api/documents", headers={"X-Role": "gestao"}).status_code == 403
    assert set(result.json()["permissions"]) == expected_permissions
    cookie = result.headers["set-cookie"]
    assert all(part in cookie for part in ("HttpOnly", "Secure", "SameSite=strict", "Max-Age=900"))
    assert client.get("/eu").json() == result.json()
    assert client.get("/conflitos?ver_para=gestao", headers={"X-Role": "gestao"}).status_code == alerts_status


@pytest.mark.parametrize(
    "invalid",
    [
        {"iss": "outro"},
        {"aud": "outro"},
        {"exp": 1},
        {"groups": ["sem-permissao"]},
        {"groups": "clause-gestao-acervo"},
        {"name": None},
        {"wrong_key": True},
    ],
)
def test_rejects_bad_assertions_without_cookie(client, invalid):
    now = datetime.now(timezone.utc)
    wrong_key = invalid.get("wrong_key")
    claims = {
        "sub": "a",
        "name": "Pessoa",
        "groups": ["clause-empregados"],
        "iss": ASSERTION_ISSUER,
        "aud": ASSERTION_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(seconds=60),
        **invalid,
    }
    secret = "x" * 32 if wrong_key else get_settings().auth_demo_sso_secret.get_secret_value()
    result = client.post("/auth/callback", json={"token": jwt.encode(claims, secret, algorithm="HS256")})
    assert result.status_code == 401
    assert "set-cookie" not in result.headers


def test_tokens_cannot_cross_the_callback_and_session_boundary(client):
    token = assertion(client)
    assert client.get("/eu", headers={"Cookie": f"ipbot_session={token}"}).status_code == 401
    assert client.post("/auth/callback", json={"token": token}).status_code == 200
    session = client.cookies.get("ipbot_session")
    assert client.post("/auth/callback", json={"token": session}).status_code == 401


def test_acervo_denies_anonymous_requests_and_ignores_browser_identity(client):
    identifier = uuid4()
    headers = {"X-Role": "gestao", "X-Name": "Gestao"}
    for path in (
        "/api/topics",
        f"/api/documents?topic_id={identifier}",
        f"/api/documents/{identifier}/file",
        "/conflitos",
    ):
        assert client.get(path, headers=headers).status_code == 401
    assert client.post("/api/questions", json={"topic_id": str(identifier), "question": "Prazo?"}).status_code == 401
    assert client.post("/api/documents").status_code == 401
    assert client.post("/api/auth/demo/assertion", json={"user_id": "a", "role": "gestao"}).status_code == 422
    assert client.post("/auth/callback", json={"token": assertion(client), "name": "Gestão"}).status_code == 422
    assert client.post("/api/auth/demo/assertion", json={"user_id": "missing"}).status_code == 404


def test_disabling_demo_rejects_callback_and_existing_session(client, monkeypatch):
    token = assertion(client)
    assert client.post("/auth/callback", json={"token": token}).status_code == 200
    monkeypatch.setattr(get_settings(), "auth_demo_enabled", False)
    assert client.get("/api/auth/demo/users").status_code == 404
    assert client.post("/api/auth/demo/assertion", json={"user_id": "a"}).status_code == 404
    assert client.post("/auth/callback", json={"token": token}).status_code == 404
    assert client.get("/eu").status_code == 401


def test_direct_pdf_returns_the_same_original_for_all_profiles(client, tmp_path, monkeypatch):
    identifier = uuid4()
    content = make_pdf(["Original da versao."])
    (tmp_path / "original.pdf").write_bytes(content)
    # A consulta de originais usa SQL comum; o teste exercita o arquivo real sem depender do worker.
    engine = create_engine(f"sqlite:///{(tmp_path / 'acervo.sqlite').as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE document_versions (id TEXT, storage_key TEXT, filename TEXT)"))
            connection.execute(
                text("INSERT INTO document_versions VALUES (:id, 'original.pdf', 'original.pdf')"),
                {"id": identifier.hex},
            )
        # O adaptador de teste faz no SQLite a conversão de UUID que o psycopg faz no PostgreSQL.
        from sqlalchemy import event

        @event.listens_for(engine, "before_execute", retval=True)
        def bind_uuid(connection, clause, multiparams, params, options):
            if isinstance(params.get("id"), type(identifier)):
                clause = clause.bindparams(bindparam("id", type_=Uuid))
            return clause, multiparams, params

        monkeypatch.setattr(main, "get_engine", lambda: engine)
        monkeypatch.setattr(get_settings(), "storage_path", tmp_path)
        path = f"/api/documents/{identifier}/file"
        assert client.get(path).status_code == 401
        for account in ("a", "b", "c"):
            assert client.post("/auth/callback", json={"token": assertion(client, account)}).status_code == 200
            response = client.get(path)
            assert response.status_code == 200 and response.content == content
            assert response.headers["cache-control"] == "private, no-store"
    finally:
        engine.dispose()
