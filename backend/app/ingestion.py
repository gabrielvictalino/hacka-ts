import hashlib
import json
import os
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from pypdf import PdfReader
from sqlalchemy import text

from app.config import get_settings
from app.contracts import IngestionResult
from app.document_parser import page_passages, read_header


class InvalidDocument(ValueError):
    pass


def update_metadata(connection, job, first_page: str, *, preserve_existing_citations: bool = False) -> None:
    """Enriquece a edição sem alterar páginas, trechos ou referências curadas."""
    metadata = read_header(first_page)
    metadata["title"] = metadata["title"] or job["filename"]
    document_id = job["document_id"]
    conflict_error = None
    if metadata["code"]:
        # Upsert serializa edições do mesmo código, inclusive entre workers.
        document_id = connection.execute(
            text("""INSERT INTO documents(id, topic_id, title, code)
                VALUES (:id, :topic_id, :title, :code)
                ON CONFLICT(topic_id, code) DO UPDATE SET code=EXCLUDED.code RETURNING id"""),
            {"id": uuid4(), "topic_id": job["topic_id"], "title": metadata["title"], "code": metadata["code"]},
        ).scalar_one()
        conflict = connection.execute(
            text("""SELECT id FROM document_versions v WHERE document_id=:document AND version=:version
                AND (status='ready' OR EXISTS (SELECT 1 FROM pages WHERE version_id=v.id))
                AND id<>:id ORDER BY created_at, id LIMIT 1"""),
            {"document": document_id, "version": metadata["version"], "id": job["id"]},
        ).scalar()
        if conflict:
            if not preserve_existing_citations:
                raise InvalidDocument(
                    "Código e versão já publicados com outro conteúdo. Confira a edição do documento."
                )
            conflict_error = (
                f"Conflito de metadados: {metadata['code']} v{metadata['version']} já consta na versão {conflict} "
                "com outro conteúdo. Fonte legada e citações preservadas; confira a edição antes de reenviar."
            )
    connection.execute(
        text("""UPDATE document_versions SET document_id=:document_id, title=:title, version=:version,
            document_type=:document_type, document_layer=:document_layer, declared_phase=:declared_phase,
            valid_from=:valid_from, valid_until=:valid_until, linked_codes=CAST(:linked_codes AS jsonb),
            processed_pages=CASE WHEN status='ready' THEN page_count ELSE processed_pages END,
            status=CASE WHEN CAST(:conflict_error AS text) IS NOT NULL THEN 'failed' ELSE status END,
            error=COALESCE(:conflict_error, error)
            WHERE id=:id"""),
        {
            **metadata,
            "linked_codes": json.dumps(metadata["linked_codes"]),
            "id": job["id"],
            "document_id": document_id,
            "conflict_error": conflict_error,
        },
    )
    if document_id != job["document_id"]:
        connection.execute(
            text("""DELETE FROM documents WHERE id=:id AND NOT EXISTS
                (SELECT 1 FROM document_versions WHERE document_id=:id)"""),
            {"id": job["document_id"]},
        )


def backfill_metadata(connection) -> None:
    # Usa o texto já publicado: não depende do original em disco nem recorta citações novamente.
    versions = (
        connection.execute(
            text("""SELECT v.id, v.document_id, v.topic_id, v.filename, p.text FROM document_versions v
            JOIN pages p ON p.version_id=v.id AND p.physical_page=1
            WHERE v.status='ready' AND v.title IS NULL ORDER BY v.topic_id, v.created_at, v.id FOR UPDATE OF v"""),
        )
        .mappings()
        .all()
    )
    for version in versions:
        update_metadata(connection, version, version["text"], preserve_existing_citations=True)


def enqueue(connection, topic_id: UUID, filename: str, content: bytes) -> IngestionResult:
    settings = get_settings()
    if not content or len(content) > settings.max_upload_bytes:
        raise InvalidDocument("O arquivo deve ter entre 1 byte e 25 MiB.")
    if not content.startswith(b"%PDF-"):
        raise InvalidDocument("O arquivo não é um PDF válido.")
    if not connection.execute(text("SELECT id FROM topics WHERE id=:id"), {"id": topic_id}).scalar():
        raise InvalidDocument("Tema não encontrado.")
    digest = hashlib.sha256(content).hexdigest()
    # Serializa somente reenvios do mesmo conteúdo no mesmo tema.
    connection.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {
            "key": int.from_bytes(
                hashlib.sha256(f"{topic_id}:{digest}".encode()).digest()[:8],
                signed=True,
            )
        },
    )
    previous = (
        connection.execute(
            text("""
        SELECT id, document_id, topic_id, filename, title, status, error FROM document_versions WHERE topic_id=:topic AND sha256=:sha FOR UPDATE
    """),
            {"topic": topic_id, "sha": digest},
        )
        .mappings()
        .first()
    )
    storage_key = f"{digest}.pdf"
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    target = settings.storage_path / storage_key
    # Restaura originais ausentes ou corrompidos antes de reutilizá-los em qualquer tema.
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        _store_original(target, content)
    if previous:
        if previous["status"] == "ready" and previous["title"] is None:
            first_page = connection.execute(
                text("SELECT text FROM pages WHERE version_id=:id AND physical_page=1"),
                previous,
            ).scalar_one()
            update_metadata(connection, previous, first_page, preserve_existing_citations=True)
            previous = (
                connection.execute(
                    text("SELECT id, status, error FROM document_versions WHERE id=:id"),
                    previous,
                )
                .mappings()
                .one()
            )
        if previous["status"] == "failed":
            # Fontes legadas em conflito já têm citações publicadas. Nunca as recria no worker.
            if connection.execute(
                text("SELECT EXISTS (SELECT 1 FROM pages WHERE version_id=:id)"),
                previous,
            ).scalar_one():
                return IngestionResult(
                    version_id=previous["id"],
                    status="failed",
                    duplicate=True,
                    error=previous["error"],
                )
            connection.execute(
                text(
                    "UPDATE document_versions SET status='queued', error=NULL, processed_pages=0, page_count=NULL WHERE id=:id"
                ),
                previous,
            )
            return IngestionResult(version_id=previous["id"], status="queued", duplicate=True)
        return IngestionResult(
            version_id=previous["id"],
            status=previous["status"],
            duplicate=True,
            error=previous["error"],
        )

    document_id, version_id = uuid4(), uuid4()
    safe_name = Path(filename.replace("\\", "/")).name
    connection.execute(
        text("INSERT INTO documents(id, topic_id, title) VALUES (:id, :topic, :title)"),
        {"id": document_id, "topic": topic_id, "title": safe_name},
    )
    connection.execute(
        text("""
        INSERT INTO document_versions(id, document_id, topic_id, filename, storage_key, sha256)
        VALUES (:id, :document, :topic, :filename, :key, :sha)
    """),
        {
            "id": version_id,
            "document": document_id,
            "topic": topic_id,
            "filename": safe_name,
            "key": storage_key,
            "sha": digest,
        },
    )
    return IngestionResult(version_id=version_id, status="queued")


def _store_original(target: Path, content: bytes) -> None:
    settings = get_settings()
    temporary = settings.storage_path / f".{uuid4()}.tmp"
    try:
        temporary.write_bytes(content)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def extract_pages(content: bytes) -> list[str]:
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise InvalidDocument("PDF protegido por senha; envie uma cópia sem proteção.")
        pages = [(page.extract_text() or "") for page in reader.pages]
    except InvalidDocument:
        raise
    except Exception as exc:
        raise InvalidDocument("Não foi possível ler o PDF; verifique o arquivo original.") from exc
    if any("\x00" in page for page in pages):
        raise InvalidDocument("PDF contém caracteres nulos no texto; gere uma nova cópia pesquisável.")
    if not pages or not any(page.strip() for page in pages):
        raise InvalidDocument("PDF sem texto extraível; OCR ainda não está disponível.")
    return pages


def passages_for_page(page: str, size: int = 1500):
    # Compatibilidade com consumidores da fundação; size não corta itens completos.
    for _, excerpt in page_passages(page):
        yield excerpt
