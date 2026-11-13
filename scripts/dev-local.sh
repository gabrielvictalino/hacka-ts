#!/usr/bin/env bash
# Ambiente local do IPBOT sem Docker nem sudo: PostgreSQL exclusivo de desenvolvimento,
# worker, API e frontend. Guia completo: docs/ambiente-sem-docker.md
#
# Configuração por variáveis de ambiente (todas opcionais):
#   IPBOT_STATE_DIR      estado local: banco, credenciais, logs, PIDs, binários e PDFs enviados
#                        (padrão: ${XDG_DATA_HOME:-$HOME/.local/share}/ipbot-dev, fora do repositório)
#   IPBOT_DB             banco usado pela aplicação e pelos testes (padrão: ipbot_dev)
#   IPBOT_PG_PORT        porta do PostgreSQL em 127.0.0.1 (padrão: 55432)
#   IPBOT_API_PORT       porta da API em 127.0.0.1 (padrão: 8000)
#   IPBOT_FRONTEND_PORT  porta do Vite em 127.0.0.1 (padrão: 5173)
#   IPBOT_PG_BIN         pasta com initdb/pg_ctl/psql já instalados (padrão: PATH ou pgserver)
#   IPBOT_PYTHON         Python da aplicação (padrão: .venv/bin/python do repositório)
#
# Nenhum valor secreto é impresso. A senha do banco é gerada e guardada em $IPBOT_STATE_DIR/postgres.env (0600).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="${IPBOT_STATE_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/ipbot-dev}"
DB="${IPBOT_DB:-ipbot_dev}"
PG_PORT="${IPBOT_PG_PORT:-55432}"
# Nomes distintos de API_PORT/FRONTEND_PORT do .env, que é carregado depois e não pode sobrescrevê-los.
LOCAL_API_PORT="${IPBOT_API_PORT:-8000}"
LOCAL_FRONTEND_PORT="${IPBOT_FRONTEND_PORT:-5173}"
PY="${IPBOT_PYTHON:-$ROOT/.venv/bin/python}"
PGSERVER_VERSION="0.1.4"
ROLE="ipbot_dev"

PG_DATA="$STATE/pgdata"
PG_SOCK="$STATE/pgsock"
PG_LOG="$STATE/logs/postgres.log"
PG_VENV="$STATE/pg-venv"
CREDS="$STATE/postgres.env"
LOGS="$STATE/logs"
RUN="$STATE/run"

die() { echo "erro: $*" >&2; exit 1; }
need_root_env() { [ -f "$ROOT/.env" ] || die ".env ausente. Crie com: python3 scripts/init_env.py"; }

pg_bin() {
  if [ -n "${IPBOT_PG_BIN:-}" ]; then echo "$IPBOT_PG_BIN"; return; fi
  local found
  found="$(ls -d "$PG_VENV"/lib/python3*/site-packages/pgserver/pginstall/bin 2>/dev/null | head -1 || true)"
  if [ -n "$found" ]; then echo "$found"; return; fi
  if command -v pg_ctl >/dev/null 2>&1; then dirname "$(command -v pg_ctl)"; return; fi
  die "binários do PostgreSQL não encontrados. Rode: $0 setup-postgres (ou defina IPBOT_PG_BIN)"
}

pg_ctl_() { "$(pg_bin)/pg_ctl" -D "$PG_DATA" "$@"; }
pg_running() { [ -d "$PG_DATA" ] && pg_ctl_ status >/dev/null 2>&1; }
psql_admin() { "$(pg_bin)/psql" -h "$PG_SOCK" -p "$PG_PORT" -U postgres -v ON_ERROR_STOP=1 -q "$@"; }

pg_start() {
  [ -d "$PG_DATA" ] || die "cluster ainda não criado. Rode: $0 init-db"
  if pg_running; then echo "postgres já está em execução em 127.0.0.1:$PG_PORT"; return; fi
  mkdir -p "$PG_SOCK" "$LOGS"
  pg_ctl_ -l "$PG_LOG" -o "-c listen_addresses=127.0.0.1 -p $PG_PORT -k $PG_SOCK" -w start >/dev/null
  echo "postgres em execução em 127.0.0.1:$PG_PORT"
}

pg_stop() {
  if pg_running; then pg_ctl_ -m fast -w stop >/dev/null; echo "postgres parado (dados preservados)"
  else echo "postgres não estava em execução"; fi
}

create_db() { # nome
  local name="$1"
  [[ "$name" =~ ^[a-z_][a-z0-9_]*$ ]] || die "nome de banco inválido: $name"
  pg_start >/dev/null
  if [ "$(psql_admin -tA -c "SELECT 1 FROM pg_database WHERE datname='$name'")" = "1" ]; then
    echo "banco $name já existe"
  else
    psql_admin -c "CREATE DATABASE \"$name\" OWNER \"$ROLE\""
    echo "banco $name criado"
  fi
}

load_env() { # exporta .env do repositório e credenciais do banco local, sem imprimir valores
  need_root_env
  [ -f "$CREDS" ] || die "credenciais do banco local ausentes. Rode: $0 init-db"
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  # shellcheck disable=SC1090
  . "$CREDS"
  set +a
  export POSTGRES_DB="$DB" STORAGE_PATH="$STATE/storage/$DB" PYTHONPATH="$ROOT/backend"
  mkdir -p "$STORAGE_PATH"
}

alive() { [ -f "$RUN/$1.pid" ] && kill -0 "$(cat "$RUN/$1.pid")" 2>/dev/null; }

launch() { # nome, pasta, comando...
  local name="$1" dir="$2"; shift 2
  if alive "$name"; then echo "$name já está em execução (PID $(cat "$RUN/$name.pid"))"; return; fi
  mkdir -p "$LOGS" "$RUN"
  ( cd "$dir" && setsid nohup "$@" >>"$LOGS/$name.log" 2>&1 </dev/null & echo $! >"$RUN/$name.pid" )
  echo "$name iniciado (PID $(cat "$RUN/$name.pid")) · log $LOGS/$name.log"
}

halt() {
  local name="$1" pid
  if alive "$name"; then
    pid="$(cat "$RUN/$name.pid")"
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    echo "$name parado"
  else
    echo "$name não estava em execução"
  fi
  rm -f "$RUN/$name.pid"
}

port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

# Pronto só se o próprio processo continuar vivo: uma resposta de outro serviço na porta não conta.
wait_ready() { # nome, url, segundos
  for _ in $(seq "$3"); do
    alive "$1" || return 1
    curl -s -o /dev/null --max-time 2 "$2" && alive "$1" && return 0
    sleep 1
  done
  return 1
}

case "${1:-}" in
  setup-postgres)
    # Binários oficiais do PostgreSQL 16 empacotados em pgserver, instalados fora do repositório.
    if [ -n "$(ls -d "$PG_VENV"/lib/python3*/site-packages/pgserver 2>/dev/null || true)" ]; then
      echo "pgserver já instalado em $PG_VENV"
    elif command -v uv >/dev/null 2>&1; then
      uv venv --python 3.12 "$PG_VENV" >/dev/null && uv pip install --python "$PG_VENV/bin/python" -q "pgserver==$PGSERVER_VERSION"
    else
      python3 -m venv "$PG_VENV" && "$PG_VENV/bin/pip" install -q "pgserver==$PGSERVER_VERSION"
    fi
    "$(pg_bin)/postgres" --version
    ;;
  init-db)
    BIN="$(pg_bin)"
    if [ -d "$PG_DATA" ]; then echo "cluster já existe em $PG_DATA; nada alterado"
    else
      mkdir -p "$STATE" "$PG_SOCK" "$LOGS"
      ( umask 077
        "$BIN/initdb" -D "$PG_DATA" -U postgres --auth-local=trust --auth-host=scram-sha-256 -E UTF8 --locale=C.UTF-8 >/dev/null
        # Alguns ambientes limpam /dev/shm ao fim de cada sessão; memória mapeada no diretório de dados evita a perda.
        printf '\n# IPBOT local\ndynamic_shared_memory_type = mmap\nshared_memory_type = mmap\n' >>"$PG_DATA/postgresql.conf" )
      pg_start
      PASSWORD="$("$PY" -c 'import secrets; print(secrets.token_hex(24))' 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(24))')"
      psql_admin -v role="$ROLE" -v pass="$PASSWORD" <<'SQL'
CREATE ROLE :"role" LOGIN PASSWORD :'pass';
SQL
      ( umask 077
        printf 'POSTGRES_HOST=127.0.0.1\nPOSTGRES_PORT=%s\nPOSTGRES_USER=%s\nPOSTGRES_PASSWORD=%s\n' "$PG_PORT" "$ROLE" "$PASSWORD" >"$CREDS" )
      unset PASSWORD
      echo "cluster criado; credenciais em $CREDS (0600, não versionar)"
    fi
    create_db "$DB"
    ;;
  create-db) create_db "${2:?informe o nome do banco}" ;;
  pg-start) pg_start ;;
  pg-stop) pg_stop ;;
  migrate)
    pg_start >/dev/null; load_env; cd "$ROOT"
    "$PY" -m alembic -c backend/alembic.ini upgrade heads
    "$PY" -m alembic -c backend/alembic.ini current
    ;;
  test)
    # Use um banco só para os testes e mantenha o worker parado ou apontando para outro banco.
    pg_start >/dev/null; load_env; cd "$ROOT"; shift
    "$PY" -m pytest backend/tests -o addopts="" -q -p no:cacheprovider "$@"
    ;;
  import)
    [ -n "${2:-}" ] || die "informe a pasta do acervo (com ferias/, inovacao/ e locacao/)"
    pg_start >/dev/null; load_env; cd "$ROOT"
    "$PY" -m app.import_collection "$2"
    ;;
  run) pg_start >/dev/null; load_env; cd "$ROOT"; shift; exec "$@" ;;
  start)
    pg_start; load_env
    [ -d "$ROOT/frontend/node_modules" ] || die "dependências do frontend ausentes. Rode: (cd frontend && npm ci)"
    for port in "$LOCAL_API_PORT" "$LOCAL_FRONTEND_PORT"; do
      if port_busy "$port" && ! { alive api || alive frontend; }; then
        die "porta $port já está em uso por outro processo. Escolha outra com IPBOT_API_PORT/IPBOT_FRONTEND_PORT."
      fi
    done
    launch worker "$ROOT" "$PY" -m app.worker
    launch api "$ROOT" "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$LOCAL_API_PORT"
    launch frontend "$ROOT/frontend" env API_PROXY_TARGET="http://127.0.0.1:$LOCAL_API_PORT" \
      npx vite --host 127.0.0.1 --port "$LOCAL_FRONTEND_PORT" --strictPort
    failed=0
    if wait_ready api "http://127.0.0.1:$LOCAL_API_PORT/health/ready" 30; then echo "API pronta em http://127.0.0.1:$LOCAL_API_PORT"
    else echo "API não ficou pronta; veja $LOGS/api.log" >&2; failed=1; fi
    if wait_ready frontend "http://127.0.0.1:$LOCAL_FRONTEND_PORT/" 30; then
      echo "frontend pronto em http://127.0.0.1:$LOCAL_FRONTEND_PORT (banco $DB)"
    else echo "frontend não ficou pronto; veja $LOGS/frontend.log" >&2; failed=1; fi
    alive worker || { echo "worker não está em execução; veja $LOGS/worker.log" >&2; failed=1; }
    exit "$failed"
    ;;
  stop) halt frontend; halt api; halt worker; pg_stop ;;
  status)
    pg_running && echo "postgres: em execução em 127.0.0.1:$PG_PORT" || echo "postgres: parado"
    for s in worker api frontend; do alive "$s" && echo "$s: em execução (PID $(cat "$RUN/$s.pid"))" || echo "$s: parado"; done
    echo "estado: $STATE"
    ;;
  *)
    cat <<EOF
Uso: $0 <comando>
  setup-postgres   instala binários do PostgreSQL 16 (pgserver==$PGSERVER_VERSION) em \$IPBOT_STATE_DIR
  init-db          cria o cluster, o usuário e o banco \$IPBOT_DB (gera a senha localmente)
  create-db NOME   cria outro banco no mesmo cluster
  pg-start|pg-stop inicia ou para só o PostgreSQL
  migrate          aplica as migrações (upgrade heads) no banco \$IPBOT_DB
  test [args]      executa pytest backend/tests no banco \$IPBOT_DB
  import PASTA     importa o acervo local para o banco \$IPBOT_DB
  run CMD...       executa um comando com o .env e o banco local
  start|stop|status  PostgreSQL, worker, API e frontend
EOF
    exit 2
    ;;
esac
