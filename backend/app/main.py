import hashlib
import logging
from typing import Annotated
from uuid import UUID, uuid4

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
    BatchFileResult,
    DocumentVersion,
    IngestionResult,
    QuestionRequest,
    QuestionResponse,
    Topic,
    TopicRequest,
)
from app.db import get_engine, get_migration_config
from app.fatos.api import router as facts_router
from app.ingestion import InvalidDocument, enqueue
from app.regras.api import router as rules_router

logger = logging.getLogger(__name__)

app = FastAPI(title="IPBOT API", version="0.1.0")
app.include_router(auth_router)
app.include_router(facts_router)
app.include_router(rules_router)


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


@app.post("/api/topics", response_model=Topic, dependencies=[Depends(require_management)], tags=["ingestion"])
def create_topic(body: TopicRequest):
    with get_engine().begin() as connection:
        return (
            connection.execute(
                text("""INSERT INTO topics(id, name) VALUES (:id, :name)
                ON CONFLICT(name) DO UPDATE SET name=EXCLUDED.name RETURNING id, name"""),
                {"id": uuid4(), "name": body.name.strip()},
            )
            .mappings()
            .one()
        )


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
            SELECT v.id, v.document_id, v.topic_id, v.filename, COALESCE(v.title, d.title) AS title, d.code,
                   v.version, v.status, v.page_count, v.error, v.document_type, v.document_layer,
                   v.declared_phase, v.valid_from, v.valid_until, v.linked_codes, v.processed_pages
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


@app.post(
    "/api/documents/batch",
    response_model=list[BatchFileResult],
    status_code=202,
    dependencies=[Depends(require_management)],
    tags=["ingestion"],
)
async def upload_batch(topic_id: Annotated[UUID, Form()], files: Annotated[list[UploadFile], File()]):
    results = []
    try:
        for file in files:
            filename = file.filename or "documento.pdf"
            try:
                content = await file.read(get_settings().max_upload_bytes + 1)
                result = await run_in_threadpool(_enqueue_upload, topic_id, filename, content)
                results.append(BatchFileResult(filename=filename, result=result))
            except InvalidDocument as exc:
                results.append(BatchFileResult(filename=filename, error=str(exc)))
            except SQLAlchemyError:
                logger.exception("Falha de banco ao enfileirar %s", filename)
                results.append(BatchFileResult(filename=filename, error="Banco indisponível; reenvie o PDF."))
            except OSError:
                results.append(BatchFileResult(filename=filename, error="Armazenamento indisponível; reenvie o PDF."))
    finally:
        for file in files:
            await file.close()
    return results


@app.post(
    "/api/documents/{version_id}/retry",
    response_model=IngestionResult,
    status_code=202,
    dependencies=[Depends(require_management)],
    tags=["ingestion"],
)
def retry_document(version_id: UUID):
    with get_engine().connect() as connection:
        row = (
            connection.execute(
                text("SELECT topic_id, filename, storage_key, sha256 FROM document_versions WHERE id=:id"),
                {"id": version_id},
            )
            .mappings()
            .first()
        )
    if not row:
        raise HTTPException(404, "Versão não encontrada.")
    try:
        path = get_settings().storage_path / row["storage_key"]
        with path.open("rb") as stream:
            content = stream.read(get_settings().max_upload_bytes + 1)
        if hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise InvalidDocument("Original corrompido; selecione e reenvie o PDF para restaurá-lo.")
        return _enqueue_upload(row["topic_id"], row["filename"], content)
    except OSError as exc:
        raise HTTPException(422, "Original indisponível; selecione e reenvie o PDF.") from exc
    except InvalidDocument as exc:
        raise HTTPException(422, str(exc)) from exc


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
