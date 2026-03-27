#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

report_process() {
  local name="$1"
  local pid_file="$2"
  local port="$3"

  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      echo "$name.pid=$pid"
      echo "$name.process=running"
    else
      echo "$name.pid=${pid:-unknown}"
      echo "$name.process=stale"
    fi
  else
    echo "$name.pid=none"
    echo "$name.process=stopped"
  fi

  local listening
  listening="$(lsof -iTCP:"$port" -sTCP:LISTEN -n -P 2>/dev/null | awk 'NR==2 {print $2}' || true)"
  echo "$name.port=$port"
  echo "$name.listener=${listening:-none}"
}

report_http() {
  local name="$1"
  local url="$2"
  if response="$(curl -fsS --max-time 2 "$url" 2>/dev/null)"; then
    echo "$name.http=ok"
    echo "$name.url=$url"
    echo "$name.response=$response"
  else
    echo "$name.http=down"
    echo "$name.url=$url"
  fi
}

report_process backend "$RUN_DIR/backend.pid" "$BACKEND_PORT"
report_http backend "http://$BACKEND_HOST:$BACKEND_PORT/health"

report_process frontend "$RUN_DIR/frontend.pid" "$FRONTEND_PORT"
report_http frontend "http://$FRONTEND_HOST:$FRONTEND_PORT"