from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, Depends, HTTPException

from app.config import get_settings
from app.contracts import Identity, Permission, Role


def permissions_for(role: Role) -> list[Permission]:
    return list(Permission) if role == Role.gestao else [Permission.read]


def issue_demo_token(user_id: str) -> str:
    settings = get_settings()
    account = settings.auth_demo_users.get(user_id)
    if not settings.auth_demo_enabled or account is None:
        raise HTTPException(404, "Simulador ou conta indisponível.")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "name": account["name"],
            "role": Role(account["role"]),
            "simulated": True,
            "iss": "ipbot-local-demo",
            "aud": "ipbot-api",
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        settings.auth_secret.get_secret_value(),
        algorithm="HS256",
    )


def current_identity(ipbot_session: str | None = Cookie(default=None)) -> Identity:
    settings = get_settings()
    try:
        if not ipbot_session or not settings.auth_demo_enabled:
            raise ValueError("Sessão ausente")
        claims = jwt.decode(
            ipbot_session,
            settings.auth_secret.get_secret_value(),
            algorithms=["HS256"],
            issuer="ipbot-local-demo",
            audience="ipbot-api",
            options={
                "require": [
                    "exp",
                    "iat",
                    "sub",
                    "iss",
                    "aud",
                    "role",
                    "name",
                    "simulated",
                ]
            },
        )
        role = Role(claims["role"])
        return Identity(
            subject=claims["sub"],
            name=claims["name"],
            role=role,
            permissions=permissions_for(role),
            simulated=claims["simulated"],
        )
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(401, "Identidade inválida ou sessão expirada.") from None


def require_ingestion(identity: Identity = Depends(current_identity)) -> Identity:
    if Permission.ingest not in identity.permissions:
        raise HTTPException(403, "Somente Gestão pode importar documentos.")
    return identity
