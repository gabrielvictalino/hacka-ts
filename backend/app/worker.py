import hashlib
import logging
import signal
import sys
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import get_engine
from app.document_parser import page_passages
from app.ingestion import InvalidDocument, extract_pages, update_metadata

logger = logging.getLogger(__name__)
HEARTBEAT = Path("/tmp/ipbot-worker-heartbeat")


def _progress(version_id, **values):
    with get_engine().begin() as connection:
        connection.execute(
            text("""UPDATE document_versions SET processed_pages=:processed_pages,
                page_count=:page_count WHERE id=:id"""),
            {"id": version_id, **values},
        )


def _publish(connection, job, pages):
    section = None
    for physical_page, page_text in enumerate(pages, start=1):
        page_id = uuid4()
        connection.execute(
            text("""INSERT INTO pages(id, version_id, physical_page, text)
                VALUES (:id, :version, :page, :text)"""),
            {"id": page_id, "version": job["id"], "page": physical_page, "text": page_text},
        )
        for ordinal, (section, excerpt) in enumerate(page_passages(page_text, section)):
            connection.execute(
                text("""INSERT INTO passages(id, page_id, ordinal, excerpt, section)
                    VALUES (:id, :page, :ordinal, :excerpt, :section)"""),
                {"id": uuid4(), "page": page_id, "ordinal": ordinal, "excerpt": excerpt, "section": section},
            )
        _progress(job["id"], processed_pages=physical_page, page_count=len(pages))
    update_metadata(connection, job, pages[0])
    connection.execute(
        text("""UPDATE document_versions SET status='ready', error=NULL, page_count=:count,
            processed_at=now() WHERE id=:id"""),
        {"id": job["id"], "count": len(pages)},
    )


def process_one() -> bool:
    # Lock de sessão sobrevive aos commits de progresso; a queda da conexão libera o trabalho.
    # Uma versão em processing sem lock pode ser retomada por outro worker.
    with get_engine().connect() as connection:
        job, lock_key = None, None
        skipped = []
        while True:
            candidate = (
                connection.execute(
                    text("""SELECT id, document_id, topic_id, filename, storage_key, sha256 FROM document_versions
                    WHERE status IN ('queued', 'processing') AND NOT (id = ANY(CAST(:skipped AS uuid[])))
                    ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED"""),
                    {"skipped": skipped},
                )
                .mappings()
                .first()
            )
            if candidate is None:
                break
            key = int.from_bytes(candidate["id"].bytes[:8], signed=True)
            if connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar():
                job, lock_key = candidate, key
                break
            skipped.append(candidate["id"])
        if job is None:
            connection.rollback()
            return False
        try:
            connection.execute(
                text("""UPDATE document_versions SET status='processing', error=NULL,
                    processed_pages=0, page_count=NULL WHERE id=:id"""),
                job,
            )
            connection.commit()
            try:
                content = (get_settings().storage_path / job["storage_key"]).read_bytes()
                if hashlib.sha256(content).hexdigest() != job["sha256"]:
                    raise InvalidDocument("Original corrompido; reenvie o PDF para restaurá-lo.")
                pages = extract_pages(content)
                _progress(job["id"], processed_pages=0, page_count=len(pages))
                # Só publica páginas e trechos quando a versão inteira está persistida.
                with connection.begin():
                    _publish(connection, job, pages)
            except (InvalidDocument, OSError, SQLAlchemyError) as exc:
                connection.rollback()
                if isinstance(exc, InvalidDocument):
                    error = str(exc)
                elif isinstance(exc, OSError):
                    error = "Original indisponível no armazenamento. Reenvie o PDF."
                else:
                    logger.exception("Falha ao persistir a versão %s", job["id"])
                    error = "Falha ao persistir o documento. Reenvie o arquivo para tentar novamente."
                connection.execute(
                    text("""UPDATE document_versions SET status='failed', error=:error,
                        processed_pages=0, page_count=NULL WHERE id=:id"""),
                    {"id": job["id"], "error": error},
                )
                connection.commit()
            return True
        finally:
            connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
            connection.commit()


def main():
    if "--healthcheck" in sys.argv:
        healthy = HEARTBEAT.exists() and time.time() - HEARTBEAT.stat().st_mtime < 120
        raise SystemExit(0 if healthy else 1)
    logging.basicConfig(level=logging.INFO)
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        try:
            processed = process_one()
            HEARTBEAT.touch()
            if not processed:
                time.sleep(get_settings().worker_poll_seconds)
        except Exception:
            logger.exception("Falha no worker; transação revertida. Nova tentativa em 3 segundos.")
            time.sleep(3)


if __name__ == "__main__":
    main()
