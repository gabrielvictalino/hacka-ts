"""Cria configuração local com segredos novos sem sobrescrever um .env existente."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
content = (root / ".env.example").read_text()
content = content.replace("POSTGRES_PASSWORD=\n", f"POSTGRES_PASSWORD={secrets.token_hex(24)}\n")
content = content.replace("AUTH_SECRET=\n", f"AUTH_SECRET={secrets.token_hex(32)}\n")
target = root / ".env"
try:
    with target.open("x") as file:
        target.chmod(0o600)
        file.write(content)
except FileExistsError:
    raise SystemExit(".env já existe; nenhuma configuração foi alterada.")
print(".env criado com segredos locais. Não versione este arquivo.")
