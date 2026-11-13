#!/usr/bin/env bash
# Regressões de scripts/dev-local.sh (sem PostgreSQL, Docker ou sudo). Linux.
# Uso: bash scripts/tests/test-dev-local.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="${DEV_LOCAL_SCRIPT:-$ROOT/scripts/dev-local.sh}"
STATE="$(mktemp -d)"
export IPBOT_STATE_DIR="$STATE"
PIDS=()
failures=0

cleanup() {
  for pid in "${PIDS[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true; done
  rm -rf "$STATE"
}
trap cleanup EXIT

ok() { echo "ok   $1"; }
fail() { echo "FALHA $1"; failures=$((failures + 1)); }

free_port() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()'; }

# Grupo de processos simulando um serviço do ambiente; grava o PID do líder como o dev-local.sh grava.
fake_service() { # nome, comando de shell
  mkdir -p "$STATE/run"
  # shellcheck disable=SC2016
  setsid bash -c 'echo $$ >"$0"; '"$2" "$STATE/run/$1.pid" </dev/null >/dev/null 2>&1 &
  for _ in $(seq 50); do [ -s "$STATE/run/$1.pid" ] && break; sleep 0.1; done
  PIDS+=("$(cat "$STATE/run/$1.pid")")
}

port=$(free_port)
python3 -m http.server "$port" --bind 127.0.0.1 >/dev/null 2>&1 &
PIDS+=("$!")
for _ in $(seq 50); do (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null && break; sleep 0.1; done

# 1. Porta ocupada por processo estranho, sem serviço do ambiente vivo.
if "$SCRIPT" check-port api "$port" >/dev/null 2>&1; then fail "porta ocupada por outro processo foi aceita"
else ok "porta ocupada por outro processo é recusada"; fi

# 2. Regressão: o frontend vivo não pode liberar um processo estranho na porta da API.
fake_service frontend 'exec sleep 300'
if "$SCRIPT" check-port api "$port" >/dev/null 2>&1; then fail "frontend vivo liberou porta da API ocupada por outro processo"
else ok "frontend vivo não libera porta da API ocupada por outro processo"; fi

# 3. A porta ocupada pela própria API do ambiente é aceita (start não a duplica).
fake_service api 'exec sleep 300'
if "$SCRIPT" check-port api "$port" >/dev/null 2>&1; then ok "porta usada pela própria API é aceita"
else fail "porta usada pela própria API foi recusada"; fi

# 4. Porta livre é aceita.
if "$SCRIPT" check-port frontend "$(free_port)" >/dev/null 2>&1; then ok "porta livre é aceita"
else fail "porta livre foi recusada"; fi

# 5. Regressão: stop encerra o grupo inteiro (líder e filhos), não só o processo gravado.
fake_service worker 'sleep 300 & sleep 300 & wait'
leader="$(cat "$STATE/run/worker.pid")"
group_size() { { pgrep -g "$1" || true; } | wc -l; }
for _ in $(seq 50); do [ "$(group_size "$leader")" -ge 3 ] && break; sleep 0.1; done
children_before=$(group_size "$leader")
"$SCRIPT" stop >/dev/null 2>&1 || true
sleep 0.5
remaining=$(group_size "$leader")
if [ "$children_before" -ge 3 ] && [ "$remaining" -eq 0 ]; then ok "stop encerra o grupo de processos inteiro ($children_before processos)"
else fail "stop deixou $remaining de $children_before processos do grupo"; fi
[ ! -e "$STATE/run/worker.pid" ] && ok "stop remove o arquivo de PID" || fail "stop manteve o arquivo de PID"

echo
if [ "$failures" -eq 0 ]; then echo "todas as verificações passaram"; else echo "$failures verificação(ões) falharam"; exit 1; fi
