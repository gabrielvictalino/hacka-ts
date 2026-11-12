from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.auth import current_identity, issue_demo_token, require_ingestion
from app.config import get_settings
from app.contracts import (
    DemoSessionRequest,
    DocumentVersion,
    Identity,
    IngestionResult,
    QuestionRequest,
    QuestionResponse,
    Topic,
)
from app.db import get_engine
from app.ingestion import InvalidDocument, enqueue

app = FastAPI(title="IPBOT API", version="0.1.0")


@app.get("/health/live", tags=["health"])
def live():
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready():
    with get_engine().connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    if revision != "0001":
        raise HTTPException(503, "Migração pendente.")
    return {"status": "ready", "migration": revision}


@app.get("/api/auth/demo/users", response_model=list[Identity], tags=["identity"])
def demo_users():
    from app.auth import permissions_for
    from app.contracts import Role

    settings = get_settings()
    if not settings.auth_demo_enabled:
        raise HTTPException(404, "Simulador desativado.")
    return [
        Identity(
            subject=key,
            name=value["name"],
            role=Role(value["role"]),
            permissions=permissions_for(Role(value["role"])),
            simulated=True,
        )
        for key, value in settings.auth_demo_users.items()
    ]


@app.post("/api/auth/demo/session", response_model=Identity, tags=["identity"])
def demo_session(body: DemoSessionRequest, response: Response):
    token = issue_demo_token(body.user_id)
    response.set_cookie("ipbot_session", token, httponly=True, samesite="strict", max_age=3600)
    return current_identity(token)


@app.get("/api/auth/me", response_model=Identity, tags=["identity"])
def me(identity: Identity = Depends(current_identity)):
    return identity


@app.get(
    "/api/topics",
    response_model=list[Topic],
    dependencies=[Depends(current_identity)],
    tags=["ingestion"],
)
def topics():
    with get_engine().connect() as connection:
        return connection.execute(text("SELECT id, name FROM topics ORDER BY name")).mappings().all()


@app.get(
    "/api/documents",
    response_model=list[DocumentVersion],
    dependencies=[Depends(current_identity)],
    tags=["ingestion"],
)
def documents(topic_id: UUID):
    with get_engine().connect() as connection:
        return (
            connection.execute(
                text("""
            SELECT v.id, v.document_id, v.topic_id, v.filename, d.title, d.code,
                   v.version, v.status, v.page_count, v.error
            FROM document_versions v JOIN documents d ON d.id=v.document_id
            WHERE v.topic_id=:topic ORDER BY v.created_at DESC
        """),
                {"topic": topic_id},
            )
            .mappings()
            .all()
        )


@app.post(
    "/api/documents",
    response_model=IngestionResult,
    status_code=202,
    dependencies=[Depends(require_ingestion)],
    tags=["ingestion"],
)
async def upload(topic_id: Annotated[UUID, Form()], file: Annotated[UploadFile, File()]):
    content = await file.read(get_settings().max_upload_bytes + 1)
    try:
        with get_engine().begin() as connection:
            return enqueue(connection, topic_id, file.filename or "documento.pdf", content)
    except InvalidDocument as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()


@app.get(
    "/api/documents/{version_id}/file",
    dependencies=[Depends(current_identity)],
    response_class=FileResponse,
    tags=["ingestion"],
)
def original(version_id: UUID):
    with get_engine().connect() as connection:
        row = (
            connection.execute(
                text("SELECT storage_key, filename FROM document_versions WHERE id=:id"),
                {"id": version_id},
            )
            .mappings()
            .first()
        )
    if not row:
        raise HTTPException(404, "Versão não encontrada.")
    path = get_settings().storage_path / row["storage_key"]
    if not path.is_file():
        raise HTTPException(404, "Original indisponível.")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=row["filename"],
        content_disposition_type="inline",
    )


@app.post(
    "/api/questions",
    response_model=QuestionResponse,
    dependencies=[Depends(current_identity)],
    tags=["query"],
    responses={501: {"description": "Contrato reservado; consulta implementada em issue própria"}},
)
def question(body: QuestionRequest):
    raise HTTPException(501, "Contrato disponível; mecanismo de consulta ainda não implementado.")
