import argparse
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from app.config import get_settings
from app.db import get_engine
from app.ingestion import InvalidDocument, enqueue


def main():
    parser = argparse.ArgumentParser(description="Enfileira PDFs por subpasta/tema usando a mesma ingestão do upload.")
    parser.add_argument("path", type=Path, nargs="?", default=get_settings().collection_path)
    args = parser.parse_args()
    if args.path is None or not args.path.is_dir():
        parser.error("A pasta do acervo não existe.")
    paths = sorted(
        p for p in args.path.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf" and p.parent != args.path
    )
    if not paths:
        parser.error("Nenhum PDF em subpastas/tema; catálogo da raiz não é importado.")
    failed = False
    for path in paths:
        folder = path.relative_to(args.path).parts[0]
        topic_name = {"ferias": "Férias", "inovacao": "Inovação", "locacao": "Locação"}.get(folder, folder)
        try:
            if path.stat().st_size > get_settings().max_upload_bytes:
                raise InvalidDocument("Arquivo excede 25 MiB.")
            with get_engine().begin() as connection:
                topic_id = connection.execute(
                    text("""
                    INSERT INTO topics(id, name) VALUES (:id, :name)
                    ON CONFLICT(name) DO UPDATE SET name=EXCLUDED.name RETURNING id
                """),
                    {"id": uuid4(), "name": topic_name},
                ).scalar_one()
                result = enqueue(connection, topic_id, path.name, path.read_bytes())
            if result.status == "failed":
                failed = True
            print(
                json.dumps(
                    {
                        "file": str(path.relative_to(args.path)),
                        **result.model_dump(mode="json"),
                    },
                    ensure_ascii=False,
                )
            )
        except (InvalidDocument, OSError) as exc:
            failed = True
            print(
                json.dumps(
                    {"file": str(path), "status": "rejected", "error": str(exc)},
                    ensure_ascii=False,
                )
            )
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
