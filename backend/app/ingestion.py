import hashlib
import os
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from pypdf import PdfReader
from sqlalchemy import text

from app.config import get_settings
from app.contracts import IngestionResult


class InvalidDocument(ValueError):
    pass


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
        SELECT id, status, error FROM document_versions WHERE topic_id=:topic AND sha256=:sha
    """),
            {"topic": topic_id, "sha": digest},
        )
        .mappings()
        .first()
    )
    if previous:
        if previous["status"] == "failed":
            connection.execute(
                text("UPDATE document_versions SET status='queued', error=NULL WHERE id=:id"),
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
    storage_key = f"{digest}.pdf"
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    target = settings.storage_path / storage_key
    temporary = settings.storage_path / f".{uuid4()}.tmp"
    try:
        temporary.write_bytes(content)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
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
    if not pages or not any(page.strip() for page in pages):
        raise InvalidDocument("PDF sem texto extraível; OCR ainda não está disponível.")
    return pages


def passages_for_page(page: str, size: int = 1500):
    # Offsets sempre recortam o texto da mesma página física, sem reescrever a fonte.
    for start in range(0, len(page), size):
        excerpt = page[start : start + size].strip()
        if excerpt:
            yield excerpt
