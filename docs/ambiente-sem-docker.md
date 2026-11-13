# Ambiente local sem Docker

Alternativa ao Compose para máquinas sem Docker e sem privilégios administrativos (por exemplo, o ambiente Linux do Kiro). Usa um PostgreSQL 16 **exclusivo de desenvolvimento**, ligado só em `127.0.0.1`. O fluxo padrão continua sendo o Compose de [desenvolvimento.md](desenvolvimento.md); a CI usa o Compose.

Tudo é feito por [`scripts/dev-local.sh`](../scripts/dev-local.sh). Nunca aponte este ambiente para um banco de produção.

## Requisitos

- **Linux.** Validado em Amazon Linux 2023, x86_64. **macOS não é suportado**: o controle de processos usa `setsid` (util-linux), que o macOS não traz. Em macOS, use o Compose.
- `bash`, `setsid`, `curl`, `pgrep` (procps) e Python 3. O script verifica `setsid`, `curl` e `python3` antes de agir e recusa sistemas que não sejam Linux.
- Python 3.12 para a aplicação (recomendado via [`uv`](https://docs.astral.sh/uv/)) e Node 22+ com `npm`.
- PostgreSQL 16: o script instala os binários oficiais empacotados no pacote Python [`pgserver`](https://pypi.org/project/pgserver/) (`0.1.4`, PostgreSQL 16.2) numa venv fora do repositório. Se já houver PostgreSQL instalado, aponte `IPBOT_PG_BIN` para a pasta com `initdb`, `pg_ctl` e `psql`. O `init-db` usa a locale `C.UTF-8`, disponível nas distribuições Linux atuais.

## Onde ficam os dados

O estado local fica em `IPBOT_STATE_DIR`, por padrão `${XDG_DATA_HOME:-$HOME/.local/share}/ipbot-dev`, **fora do repositório**:

| Caminho | Conteúdo |
| --- | --- |
| `pgdata/` | Cluster do PostgreSQL (todos os bancos) |
| `postgres.env` | Usuário e senha do banco local, gerados no `init-db`, permissão `0600` |
| `storage/<banco>/` | Originais dos PDFs enviados, por banco |
| `logs/`, `run/` | Logs e PIDs de PostgreSQL, worker, API e frontend |
| `pg-venv/` | Binários do PostgreSQL (`pgserver`) |
| `pgsock/` | Socket local do PostgreSQL (só o superusuário entra por ele) |

A configuração da aplicação continua no `.env` da raiz, criado por `python3 scripts/init_env.py` e ignorado pelo Git. O script lê esse arquivo e o `postgres.env` sem imprimir valores. Não versione `.env`, banco, PDFs, logs, PIDs ou binários.

## Preparação (uma vez)

```sh
python3 scripts/init_env.py                     # só cria o .env se ainda não existir
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r backend/requirements.txt
(cd frontend && npm ci)

scripts/dev-local.sh setup-postgres             # binários do PostgreSQL 16 em IPBOT_STATE_DIR
scripts/dev-local.sh init-db                    # cluster, usuário com senha aleatória e banco ipbot_dev
scripts/dev-local.sh create-db ipbot_e2e        # opcional: banco separado para testes manuais
scripts/dev-local.sh migrate                    # alembic upgrade heads
```

O `init-db` configura `dynamic_shared_memory_type = mmap` e `shared_memory_type = mmap`. Alguns ambientes limpam `/dev/shm` ao fim de cada sessão de terminal, e o PostgreSQL perderia seus segmentos de memória compartilhada (erro `could not open shared memory segment`).

## Testes do backend

Use um banco só para a suíte e não deixe um worker consumindo a fila desse mesmo banco:

```sh
scripts/dev-local.sh migrate
scripts/dev-local.sh test                       # pytest backend/tests no banco ipbot_dev
```

Para conferir migrações como a CI: `scripts/dev-local.sh run .venv/bin/alembic -c backend/alembic.ini downgrade base` e depois `migrate`.

## Outros testes

```sh
(cd frontend && npm test)                       # regras da Gestão e do "Ver para" (node --test, sem banco)
bash scripts/tests/test-dev-local.sh            # checagem de portas por serviço e stop do grupo de processos
```

Nenhum dos dois precisa de PostgreSQL. A CI ainda não executa esses testes; a ampliação da CI está na #16.

## Acervo e uso da aplicação

Use outro banco para o acervo, para não misturar dados com a suíte de testes:

```sh
export IPBOT_DB=ipbot_e2e
scripts/dev-local.sh migrate
scripts/dev-local.sh start                      # PostgreSQL, worker, API :8000 e frontend :5173
scripts/dev-local.sh import /caminho/para/documentos_desafio_2
scripts/dev-local.sh run .venv/bin/python -m app.fatos.curadoria --strict   # após concluir a extração
```

A pasta do acervo deve conter só as subpastas de tema (`ferias/`, `inovacao/`, `locacao/`), como descrito em [desenvolvimento.md](desenvolvimento.md#importação-do-acervo). Acompanhe o processamento em `GET /api/documents?topic_id=…` ou pela tela de Gestão. Abra `http://127.0.0.1:5173`.

```sh
scripts/dev-local.sh status
scripts/dev-local.sh stop                       # para tudo; os dados ficam em IPBOT_STATE_DIR
```

Portas e banco são configuráveis por `IPBOT_PG_PORT`, `IPBOT_API_PORT`, `IPBOT_FRONTEND_PORT` e `IPBOT_DB`. O `start` recusa uma porta ocupada por um processo que não seja o próprio serviço; `scripts/dev-local.sh check-port api 8000` faz a mesma verificação sem iniciar nada.

## Recuperação após reiniciar a sessão ou a máquina

1. `scripts/dev-local.sh status`. Se algo estiver parado, `scripts/dev-local.sh start` (com o mesmo `IPBOT_DB` e `IPBOT_STATE_DIR`).
2. Os processos sobrevivem ao fim de um terminal, mas **não reiniciam sozinhos após um reboot**. Depois de reiniciar a máquina, apague PIDs antigos antes do `start`, porque um número antigo pode coincidir com outro processo: `rm -f "$IPBOT_STATE_DIR"/run/*.pid`.
3. Se o PostgreSQL não subir, veja `logs/postgres.log`. O `pg_ctl` descarta sozinho um `postmaster.pid` antigo.
4. Se `IPBOT_STATE_DIR` foi perdido (máquina nova ou ambiente descartável), repita a preparação. O acervo precisa ser importado de novo e os fatos publicados outra vez; o código e a documentação vêm do Git.

A persistência depende da máquina. Arquivos sob `$HOME` normalmente persistem entre sessões, mas pastas `tmpfs` como `/tmp` são apagadas ao reiniciar. Em ambientes de evento ou descartáveis, trate o estado local como temporário: o único lugar garantido para o código é o repositório remoto.
