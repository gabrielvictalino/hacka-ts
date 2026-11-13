from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response

from app.config import get_settings
from app.contracts import AuthCallbackRequest, DemoAssertion, DemoSessionRequest, Identity, Permission, Role

router = APIRouter(tags=["identity"])
ASSERTION_ISSUER = "ipbot-local-demo"
ASSERTION_AUDIENCE = "ipbot-auth-callback"
SESSION_ISSUER = "ipbot-api"
SESSION_AUDIENCE = "ipbot-session"
ASSERTION_SECONDS = 60
SESSION_SECONDS = 900

GROUP_ROLES = {
    "clause-empregados": Role.empregado,
    "clause-gestores": Role.gestor,
    "clause-gestao-acervo": Role.gestao,
}


def _identity(subject: str, name: str, groups: list[str]) -> Identity:
    roles = {GROUP_ROLES[group] for group in groups if group in GROUP_ROLES}
    if not subject.strip() or not name.strip() or not roles:
        raise ValueError("Identidade sem grupo reconhecido.")
    role = next(role for role in (Role.gestao, Role.gestor, Role.empregado) if role in roles)
    permissions = [Permission.read]
    if role == Role.gestao:
        permissions.extend([Permission.ingest, Permission.curate, Permission.read_alerts])
    return Identity(subject=subject, name=name, role=role, permissions=permissions, simulated=True)


def _encode(payload: dict, secret: str, issuer: str, audience: str, seconds: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {**payload, "iss": issuer, "aud": audience, "iat": now, "exp": now + timedelta(seconds=seconds)},
        secret,
        algorithm="HS256",
    )


def _decode(token: str, secret: str, issuer: str, audience: str, seconds: int) -> dict:
    claims = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        issuer=issuer,
        audience=audience,
        options={"require": ["exp", "iat", "sub", "iss", "aud", "name", "groups"], "strict_aud": True},
    )
    name, groups = claims["name"], claims["groups"]
    if (
        not isinstance(claims["sub"], str)
        or not isinstance(name, str)
        or not isinstance(groups, list)
        or not all(isinstance(group, str) for group in groups)
        or not 0 < int(claims["exp"]) - int(claims["iat"]) <= seconds
    ):
        raise ValueError("Atributos de identidade inválidos.")
    return claims


def _demo_secret() -> str:
    settings = get_settings()
    if not settings.auth_demo_enabled or settings.auth_demo_sso_secret is None:
        raise HTTPException(404, "Simulador desativado.")
    return settings.auth_demo_sso_secret.get_secret_value()


@router.get("/api/auth/demo/users", response_model=list[Identity])
def demo_users(response: Response):
    _demo_secret()
    response.headers["Cache-Control"] = "no-store"
    return [
        _identity(subject, account.name, account.groups) for subject, account in get_settings().auth_demo_users.items()
    ]


@router.post("/api/auth/demo/assertion", response_model=DemoAssertion)
def demo_assertion(body: DemoSessionRequest, response: Response):
    secret = _demo_secret()
    account = get_settings().auth_demo_users.get(body.user_id)
    if account is None:
        raise HTTPException(404, "Conta de demonstração indisponível.")
    response.headers["Cache-Control"] = "no-store"
    return DemoAssertion(
        token=_encode(
            {"sub": body.user_id, "name": account.name, "groups": account.groups},
            secret,
            ASSERTION_ISSUER,
            ASSERTION_AUDIENCE,
            ASSERTION_SECONDS,
        )
    )


@router.post("/auth/callback", response_model=Identity)
def auth_callback(body: AuthCallbackRequest, response: Response):
    secret = _demo_secret()
    settings = get_settings()
    try:
        claims = _decode(body.token, secret, ASSERTION_ISSUER, ASSERTION_AUDIENCE, ASSERTION_SECONDS)
        identity = _identity(claims["sub"], claims["name"], claims["groups"])
    except (jwt.PyJWTError, ValueError, TypeError, OverflowError):
        raise HTTPException(401, "Identidade inválida ou token expirado.") from None
    session = _encode(
        {"sub": identity.subject, "name": identity.name, "groups": claims["groups"]},
        settings.auth_secret.get_secret_value(),
        SESSION_ISSUER,
        SESSION_AUDIENCE,
        SESSION_SECONDS,
    )
    response.set_cookie(
        "ipbot_session",
        session,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        max_age=SESSION_SECONDS,
    )
    response.headers["Cache-Control"] = "no-store"
    return identity


@router.post("/api/auth/demo/session", response_model=Identity)
def demo_session(body: DemoSessionRequest, response: Response):
    # Compatibilidade com os consumidores da fundação.
    assertion = demo_assertion(body, response)
    return auth_callback(AuthCallbackRequest(token=assertion.token), response)


def current_identity(ipbot_session: str | None = Cookie(default=None)) -> Identity:
    settings = get_settings()
    try:
        if not ipbot_session or not settings.auth_demo_enabled or settings.auth_demo_sso_secret is None:
            raise ValueError("Sessão ausente.")
        claims = _decode(
            ipbot_session, settings.auth_secret.get_secret_value(), SESSION_ISSUER, SESSION_AUDIENCE, SESSION_SECONDS
        )
        return _identity(claims["sub"], claims["name"], claims["groups"])
    except (jwt.PyJWTError, ValueError, TypeError, OverflowError):
        raise HTTPException(401, "Identidade inválida ou sessão expirada.") from None


@router.get("/eu", response_model=Identity)
@router.get("/api/auth/me", response_model=Identity)
def me(response: Response, identity: Identity = Depends(current_identity)):
    response.headers["Cache-Control"] = "no-store"
    return identity


def require_management(identity: Identity = Depends(current_identity)) -> Identity:
    if identity.role != Role.gestao:
        raise HTTPException(403, "Operação reservada à Gestão.")
    return identity
