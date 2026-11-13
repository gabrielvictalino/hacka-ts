"""Simula, no banco de testes ipbot_e2e, uma fonte com falha que já tem páginas (como um legado em conflito).

Uso: scripts/dev-local.sh run .venv/bin/python tests/e2e/ui/legacy_conflict.py set|restore
Só altera um PDF de teste da interface, nunca o acervo, e só roda com IPBOT_E2E_ALLOW_DB igual a POSTGRES_DB.
"""
import os
import sys

from app.db import get_engine
from sqlalchemy import text

if not os.environ.get("POSTGRES_DB") or os.environ.get("IPBOT_E2E_ALLOW_DB") != os.environ.get("POSTGRES_DB"):
    sys.exit("recusado: defina IPBOT_E2E_ALLOW_DB com o nome do banco de teste em uso")
MARK = "Conflito de edição legada (simulado para teste)."
with get_engine().begin() as c:
    if sys.argv[1] == "set":
        row = c.execute(text("""
            SELECT v.id FROM document_versions v
            WHERE v.filename = 'interface-valido.pdf' AND v.status = 'ready'
              AND EXISTS (SELECT 1 FROM pages p WHERE p.version_id = v.id)
            ORDER BY v.created_at DESC LIMIT 1""")).first()
        if not row:
            sys.exit("nenhum PDF de teste pronto encontrado")
        c.execute(text("UPDATE document_versions SET status='failed', error=:e WHERE id=:id"), {"e": MARK, "id": row.id})
        print(row.id)
    else:
        n = c.execute(text("UPDATE document_versions SET status='ready', error=NULL WHERE error=:e"), {"e": MARK}).rowcount
        print(f"restaurados: {n}")
