#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

stop_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    return 0
  fi

  local pid
  pid="$(cat "$pid_file")"
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    echo "Stopping $name (PID $pid)"
    kill "$pid" >/dev/null 2>&1 || true
  fi
  rm -f "$pid_file"
}

stop_pid_file backend "$RUN_DIR/backend.pid"
stop_pid_file frontend "$RUN_DIR/frontend.pid"

lsof -iTCP:8000 -sTCP:LISTEN -n -P | awk 'NR>1 {print $2}' | xargs -r kill >/dev/null 2>&1 || true
lsof -iTCP:3000 -sTCP:LISTEN -n -P | awk 'NR>1 {print $2}' | xargs -r kill >/dev/null 2>&1 || true

echo "Local stack stopped"