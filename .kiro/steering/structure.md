# IPBOT · estrutura e convenções

## Organização

- `backend/app/`: `main.py` (rotas principais), `contracts.py` (modelos da API), `auth.py` (SSO simulado e permissões), `ingestion.py`, `document_parser.py`, `worker.py`, `questions.py` e `question_support.py` (consulta extrativa), `bedrock.py` e `check_bedrock.py` (geração opcional), `fatos/` (catálogo curado e API), `regras/` (cálculos), `import_collection.py`.
- `backend/migrations/`: Alembic; a CI aplica, reverte e reaplica (`upgrade heads`).
- `backend/tests/`: pytest com PostgreSQL real e PDFs sintéticos gerados no teste.
- `frontend/src/`: `main.tsx`, `QuestionPanel.tsx`, `Evidence.tsx`, `ValidityPanel.tsx`, `CalculationFields.tsx`, `style.css`.
- `packages/contracts/`: OpenAPI e tipos TypeScript gerados.
- `docs/`: especificação, cenários, guia de desenvolvimento, ADRs.

## Convenções

- Branches a partir de `dev`: `<tipo>/<issue>-<descricao-kebab>` (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `style`). PR para `dev`, uma aprovação e CI verde. Ver `CONTRIBUTING.md`.
- Commits em Conventional Commits, em português: `feat(escopo): resumo`.
- Documentação e textos de interface em português.
- Não faça push, merge de PR ou deploy sem pedido explícito.
