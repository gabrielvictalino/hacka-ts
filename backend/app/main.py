from typing import Annotated
from uuid import UUID

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.auth import current_identity, require_management
from app.auth import router as auth_router
from app.config import get_settings
from app.contracts import (
    APIError,
    DocumentVersion,
    IngestionResult,
    QuestionRequest,
    QuestionResponse,
    Topic,
)
from app.db import get_engine, get_migration_config
from app.ingestion import InvalidDocument, enqueue

app = FastAPI(title="IPBOT API", version="0.1.0")
app.include_router(auth_router)


@app.get("/health/live", tags=["health"])
def live():
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready():
    expected = set(ScriptDirectory.from_config(get_migration_config()).get_heads())
    try:
        with get_engine().connect() as connection:
            applied = set(MigrationContext.configure(connection).get_current_heads())
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Banco indisponível.") from exc
    if applied != expected:
        raise HTTPException(503, "Migração pendente.")
    return {"status": "ready", "migrations": sorted(applied)}


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
    dependencies=[Depends(require_management)],
    tags=["ingestion"],
    responses={422: {"model": APIError, "description": "PDF ou tema inválido, ou erro de validação dos campos"}},
)
async def upload(topic_id: Annotated[UUID, Form()], file: Annotated[UploadFile, File()]):
    try:
        content = await file.read(get_settings().max_upload_bytes + 1)
        return await run_in_threadpool(_enqueue_upload, topic_id, file.filename or "documento.pdf", content)
    except InvalidDocument as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()


def _enqueue_upload(topic_id: UUID, filename: str, content: bytes) -> IngestionResult:
    # A conexão, os locks, o disco e o commit ficam no mesmo thread de trabalho.
    with get_engine().begin() as connection:
        return enqueue(connection, topic_id, filename, content)


@app.get(
    "/api/documents/{version_id}/file",
    dependencies=[Depends(current_identity)],
    response_class=FileResponse,
    tags=["ingestion"],
    responses={
        200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}},
        404: {"model": APIError, "description": "Versão ou original não encontrado"},
    },
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
        headers={"Cache-Control": "private, no-store"},
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


@app.get(
    "/conflitos",
    dependencies=[Depends(require_management)],
    tags=["management"],
    responses={501: {"description": "Detalhes dos alertas serão implementados na issue #15"}},
)
def management_alerts():
    raise HTTPException(501, "Detalhes dos alertas ainda indisponíveis.")
