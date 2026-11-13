# Roteiros de validação de ponta a ponta (#16)

Roteiros usados para validar a #12 e a revisão da PR #40, preparados para a #16 (validação integrada e CI). **Ainda não fazem parte da CI.**

| Roteiro | O que verifica |
| --- | --- |
| `api_roteiro.py` | 25 verificações pelas mesmas rotas do frontend: SSO simulado, permissões (401/403), temas, processamento, lote com resultado por arquivo, duplicado, falha de PDF sem texto, retry, AC-01 com citação e PDF, pergunta fora do tema |
| `ui/roteiro_ui.cjs` | 41 verificações no Chromium headless, desktop e celular: navegação Consulta/Gestão, evidência e foco, upload e retry, permissões, "Ver para" (visão presa à consulta e visão de estagiário com o item 4.12), AC-03 (#15), retry com HTTP 202 e status `failed`, ausência de rolagem horizontal e de erros no console |

## Pré-requisitos

- Ambiente em execução com o **acervo sintético importado** (Férias, Inovação e Locação) e os **fatos publicados**, por exemplo com [`scripts/dev-local.sh`](../../scripts/dev-local.sh) e um banco só para estes testes:

  ```sh
  export IPBOT_DB=ipbot_e2e
  scripts/dev-local.sh create-db ipbot_e2e && scripts/dev-local.sh migrate
  scripts/dev-local.sh start
  scripts/dev-local.sh import /caminho/para/documentos_desafio_2
  scripts/dev-local.sh run .venv/bin/python -m app.fatos.curadoria --strict   # após a extração
  ```

- SSO simulado ativo (`AUTH_DEMO_ENABLED=true`, padrão do `scripts/init_env.py`).
- Os roteiros **enviam PDFs de teste** e, no caso do retry, alteram temporariamente o estado de um desses PDFs. Use um banco descartável, nunca um banco com dados reais.

## Execução

```sh
# API (usa httpx e pypdf do backend/requirements.txt)
IPBOT_BASE_URL=http://127.0.0.1:5173 .venv/bin/python tests/e2e/api_roteiro.py

# Interface
cd tests/e2e/ui && npm ci && npm run browser && cd -
.venv/bin/python tests/e2e/ui/make_files.py tests/e2e/ui/arquivos      # PDFs de teste únicos por execução
IPBOT_E2E_ALLOW_DB=ipbot_e2e IPBOT_DB=ipbot_e2e IPBOT_BASE_URL=http://127.0.0.1:5173 \
  node tests/e2e/ui/roteiro_ui.cjs
```

Variáveis: `IPBOT_BASE_URL` (frontend), `IPBOT_E2E_FILES` (pasta dos PDFs gerados, padrão `ui/arquivos`), `IPBOT_E2E_SHOTS` (pasta para capturas de tela, opcional), `IPBOT_E2E_ALLOW_DB` (nome do banco de teste em que a simulação de conflito legado pode rodar; sem ela o passo é recusado).

O passo de retry usa `ui/legacy_conflict.py` via `scripts/dev-local.sh run`: marca um PDF de teste já processado como falha com páginas gravadas (como uma fonte legada em conflito), confere a mensagem na tela e restaura o estado.

Em máquinas mínimas sem bibliotecas gráficas, `npx playwright install-deps chromium` exige privilégios. Sem eles, é possível extrair as bibliotecas e uma fonte (por exemplo, DejaVu) dos pacotes da distribuição para uma pasta local e usar `LD_LIBRARY_PATH` e `FONTCONFIG_FILE`; sem fontes, o Chromium renderiza textos com altura zero e os seletores falham.

## Pendências para a #16

- Executar estes roteiros na CI (Compose, com acervo de teste e worker).
- Executar `cd frontend && npm test` e `bash scripts/tests/test-dev-local.sh` na CI.
- Avaliar substituir a simulação de conflito legado por uma fixture do backend.
