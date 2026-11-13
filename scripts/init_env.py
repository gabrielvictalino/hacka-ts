"""Cria configuração local com segredos novos sem sobrescrever um .env existente."""
import json
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
content = (root / ".env.example").read_text()
content = content.replace("POSTGRES_PASSWORD=\n", f"POSTGRES_PASSWORD={secrets.token_hex(24)}\n")
content = content.replace("AUTH_SECRET=\n", f"AUTH_SECRET={secrets.token_hex(32)}\n")
content = content.replace("AUTH_DEMO_SSO_SECRET=\n", f"AUTH_DEMO_SSO_SECRET={secrets.token_hex(32)}\n")
accounts = {
    secrets.token_hex(8): {"name": name, "groups": [group]}
    for name, group in (
        ("Pessoa empregada", "clause-empregados"),
        ("Pessoa gestora", "clause-gestores"),
        ("Gestão do acervo", "clause-gestao-acervo"),
    )
}
content = content.replace("AUTH_DEMO_USERS={}", f"AUTH_DEMO_USERS='{json.dumps(accounts)}'")
target = root / ".env"
try:
    with target.open("x") as file:
        target.chmod(0o600)
        file.write(content)
except FileExistsError:
    raise SystemExit(".env já existe; nenhuma configuração foi alterada.")
print(".env criado com segredos locais. Não versione este arquivo.")
