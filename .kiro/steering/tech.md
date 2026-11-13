# IPBOT · tecnologia e validação

Stack: React 19 + TypeScript + Vite (`frontend/`), FastAPI + SQLAlchemy + Alembic (`backend/`), PostgreSQL com busca `tsvector` em português, worker Python com fila no banco. Execução padrão por Docker Compose (`compose.yaml`). Guia completo: `docs/desenvolvimento.md`.

## Segurança do ambiente

- Preserve o `.env`; crie só com `python3 scripts/init_env.py` se não existir. Nunca imprima segredos nem os coloque em `VITE_*`, steering, código ou Git.
- Nunca rode `docker compose down -v` (apaga banco e originais). Antes de subir serviços, confira de qual worktree os containers do projeto `ipbot` estão montados.
- Não habilite Bedrock nem altere credenciais AWS só para desenvolver.

## Validação (mesma ordem da CI, `.github/workflows/ci.yml`)

Com Docker: seguir "Validação em ambiente isolado" em `docs/desenvolvimento.md` (projeto `ipbot-test`).

Sem Docker (ex.: máquina Linux do Kiro, sem Docker nem sudo):

```sh
# backend: .venv com Python 3.12 via uv
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r backend/requirements.txt
.venv/bin/ruff check backend && .venv/bin/ruff format --check backend
# contratos
set -a && . ./.env && set +a
PYTHONPATH=backend .venv/bin/python -m app.export_contracts > /tmp/ipbot-openapi.json
cmp packages/contracts/openapi.json /tmp/ipbot-openapi.json
(cd frontend && npm ci && npm run contracts:generate && npm run build)
git diff --exit-code -- packages/contracts
```

`pytest backend/tests` e as migrações exigem PostgreSQL real. Sem Docker, use um PostgreSQL 16 local e **exclusivo de desenvolvimento** (ligado só em `127.0.0.1`) e exporte `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` e um `STORAGE_PATH` gravável, além do `.env`. Use bancos separados para a suíte de testes e para testes manuais com o acervo. Nunca aponte para banco de produção. Detalhes do ambiente atual em `docs/handoff-kiro.md`.

## Contratos

`backend/app/contracts.py` é a fonte. Após mudar a API, regenere `packages/contracts/openapi.json` e `index.d.ts`; a CI compara os dois.
