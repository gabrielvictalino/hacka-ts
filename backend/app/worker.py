import logging
import signal
import sys
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from app.config import get_settings
from app.db import get_engine
from app.ingestion import InvalidDocument, extract_pages, passages_for_page

logger = logging.getLogger(__name__)
HEARTBEAT = Path("/tmp/ipbot-worker-heartbeat")


def process_one() -> bool:
    # O lock dura até o commit: queda do processo devolve o trabalho à fila.
    with get_engine().begin() as connection:
        job = (
            connection.execute(
                text("""
            SELECT id, storage_key FROM document_versions
            WHERE status='queued' ORDER BY created_at
            LIMIT 1 FOR UPDATE SKIP LOCKED
        """)
            )
            .mappings()
            .first()
        )
        if not job:
            return False
        connection.execute(text("UPDATE document_versions SET status='processing' WHERE id=:id"), job)
        try:
            pages = extract_pages((get_settings().storage_path / job["storage_key"]).read_bytes())
        except (InvalidDocument, OSError) as exc:
            error = str(exc) if isinstance(exc, InvalidDocument) else "Original indisponível no armazenamento."
            connection.execute(
                text("UPDATE document_versions SET status='failed', error=:error WHERE id=:id"),
                {"id": job["id"], "error": error},
            )
            return True
        for physical_page, page_text in enumerate(pages, start=1):
            page_id = uuid4()
            connection.execute(
                text("""
                INSERT INTO pages(id, version_id, physical_page, text) VALUES (:id, :version, :page, :text)
            """),
                {
                    "id": page_id,
                    "version": job["id"],
                    "page": physical_page,
                    "text": page_text,
                },
            )
            for ordinal, excerpt in enumerate(passages_for_page(page_text)):
                connection.execute(
                    text("""
                    INSERT INTO passages(id, page_id, ordinal, excerpt) VALUES (:id, :page, :ordinal, :excerpt)
                """),
                    {
                        "id": uuid4(),
                        "page": page_id,
                        "ordinal": ordinal,
                        "excerpt": excerpt,
                    },
                )
        connection.execute(
            text("""
            UPDATE document_versions SET status='ready', error=NULL, page_count=:count, processed_at=now()
            WHERE id=:id
        """),
            {"id": job["id"], "count": len(pages)},
        )
        return True


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
