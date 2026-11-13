# Roteiros de validação de ponta a ponta (#16)

Roteiros que validam o núcleo integrado (React, API, worker e PostgreSQL) pelas mesmas rotas e telas que a pessoa usuária. A CI executa os dois com o acervo sintético em toda PR (`.github/workflows/ci.yml`).

| Roteiro | O que verifica |
| --- | --- |
| `api_roteiro.py` | 25 verificações pelas mesmas rotas do frontend: SSO simulado, permissões (401/403), temas, processamento, lote com resultado por arquivo, duplicado, falha de PDF sem texto, retry, AC-01 com citação e PDF, pergunta fora do tema |
| `ui/roteiro_ui.cjs` | 41 verificações no Chromium headless, desktop e celular: navegação Consulta/Gestão, evidência e foco, upload e retry, permissões, "Ver para" (visão presa à consulta, visão de estagiário com o item 4.12 e nenhuma permissão nova), AC-03 (#15), retry com HTTP 202 e status `failed`, ausência de rolagem horizontal e de erros no console |

## Acervos

`IPBOT_E2E_ACERVO` diz aos roteiros qual acervo foi importado. As verificações são as mesmas; só mudam as contagens esperadas.

| Valor | Acervo | Uso |
| --- | --- | --- |
| `referencia` (padrão) | Acervo do desafio (Férias, Inovação e Locação), **não versionado**, com os fatos publicados | Validação manual completa |
| `sintetico` | Gerado por `acervo_sintetico.py`: NG_111 v3.0.0 e PX_1111-001 v1.0.0 em Férias (AC-01, AC-03 e item 4.12) e uma norma de teste em Inovação e em Locação | CI e qualquer máquina sem o acervo |

Os textos do acervo sintético são resumos escritos para teste, no formato de cabeçalho lido por `backend/app/document_parser.py`, e não substituem a validação com o acervo de referência. Nele, os fatos curados ficam pendentes e as mudanças de versão não aparecem.

Os roteiros **enviam PDFs de teste** e, no retry, alteram temporariamente o estado de um deles. Use sempre um banco descartável, nunca um banco com dados reais.

## Dependências

```sh
python3 -m venv /tmp/ipbot-e2e && /tmp/ipbot-e2e/bin/pip install -r tests/e2e/requirements.txt   # httpx e pypdf
(cd tests/e2e/ui && npm ci && npx playwright install chromium)   # Playwright 1.49.1
```

Em Linux sem as bibliotecas gráficas do Chromium, `npx playwright install --with-deps chromium` instala também as dependências do sistema, mas exige privilégios. Sem eles, é possível extrair as bibliotecas e uma fonte (por exemplo, DejaVu) dos pacotes da distribuição para uma pasta local e usar `LD_LIBRARY_PATH` e `FONTCONFIG_FILE`. Sem fontes, o Chromium renderiza textos com altura zero e os seletores falham.

Nos exemplos abaixo, `PY=/tmp/ipbot-e2e/bin/python`.

## Com Docker Compose (como na CI)

Na raiz do repositório, com `.env` criado por `python3 scripts/init_env.py` (SSO simulado ativo e cookie sem `Secure` para HTTP local):

```sh
docker compose up -d --wait
$PY tests/e2e/acervo_sintetico.py /tmp/ipbot-acervo
COLLECTION_PATH=/tmp/ipbot-acervo docker compose --profile tools run --rm importer

export IPBOT_E2E_ACERVO=sintetico IPBOT_BASE_URL=http://127.0.0.1:5173
$PY tests/e2e/api_roteiro.py
$PY tests/e2e/ui/make_files.py tests/e2e/ui/arquivos     # PDFs de teste únicos por execução
IPBOT_E2E_RUNNER=compose IPBOT_E2E_ALLOW_DB="$(sed -n 's/^POSTGRES_DB=//p' .env)" node tests/e2e/ui/roteiro_ui.cjs
```

Para o acervo de referência, importe a pasta do desafio em `COLLECTION_PATH`, publique os fatos (`docker compose run --rm api python -m app.fatos.curadoria --strict`, depois da extração) e use `IPBOT_E2E_ACERVO=referencia`.

Para repetir do zero, `docker compose down -v` **apaga o banco e os originais** do Compose local.

## Sem Docker (Linux, `scripts/dev-local.sh`)

Com o ambiente de [`docs/ambiente-sem-docker.md`](../../docs/ambiente-sem-docker.md) e um banco só para estes testes:

```sh
export IPBOT_DB=ipbot_e2e
scripts/dev-local.sh create-db ipbot_e2e && scripts/dev-local.sh migrate
scripts/dev-local.sh start
$PY tests/e2e/acervo_sintetico.py /tmp/ipbot-acervo
scripts/dev-local.sh import /tmp/ipbot-acervo        # ou a pasta do acervo de referência

export IPBOT_E2E_ACERVO=sintetico IPBOT_BASE_URL=http://127.0.0.1:5173
$PY tests/e2e/api_roteiro.py
$PY tests/e2e/ui/make_files.py tests/e2e/ui/arquivos
IPBOT_E2E_ALLOW_DB=ipbot_e2e node tests/e2e/ui/roteiro_ui.cjs
```

Com o acervo de referência, publique também os fatos (`scripts/dev-local.sh run .venv/bin/python -m app.fatos.curadoria --strict`) e use `IPBOT_E2E_ACERVO=referencia`.

## Variáveis

| Variável | Padrão | Uso |
| --- | --- | --- |
| `IPBOT_BASE_URL` | `http://127.0.0.1:5173` | Endereço do frontend (Vite, com proxy para a API) |
| `IPBOT_E2E_ACERVO` | `referencia` | `referencia` ou `sintetico` |
| `IPBOT_E2E_RUNNER` | `dev-local` | Onde roda a simulação de conflito legado: `dev-local` (`scripts/dev-local.sh run`) ou `compose` (`docker compose exec api`) |
| `IPBOT_E2E_ALLOW_DB` | (vazio) | Nome do banco de teste em uso. Sem ele, a simulação de conflito legado é recusada |
| `IPBOT_E2E_FILES` | `ui/arquivos` | Pasta dos PDFs gerados por `make_files.py` |
| `IPBOT_E2E_SHOTS` | (vazio) | Pasta para capturas de tela, opcional |

O passo de retry usa `ui/legacy_conflict.py`: marca um PDF de teste já processado como falha com páginas gravadas (como uma fonte legada em conflito), confere a mensagem na tela e restaura o estado. Ele só altera o PDF de teste da interface e só roda quando `IPBOT_E2E_ALLOW_DB` é igual ao banco configurado.

## Outros testes executados na CI

```sh
(cd frontend && npm test)              # regras puras do frontend com node:test (Node 22 ou mais novo)
bash scripts/tests/test-dev-local.sh   # regressões de scripts/dev-local.sh (Linux)
```

## Pendências da #16

- Sessão inválida e acesso direto ao PDF sem sessão pela interface; perfil gestor nos roteiros.
- Perspectivas Prazos e Valores, fatos curados e mudanças de versão (dependem do acervo de referência e da #21/#37).
- Falha simulada do Bedrock com consulta extrativa e abertura de evidências.
- Avaliar substituir a simulação de conflito legado por uma fixture do backend.
