#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/logs"
BACKEND_DIR="$ROOT_DIR/backend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-$BACKEND_DIR/.env}"

mkdir -p "$RUN_DIR" "$LOG_DIR"

if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
  echo "Missing backend env file: $BACKEND_ENV_FILE" >&2
  exit 1
fi

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi

echo "Using Python: $PYTHON_BIN"
echo "Applying backend migrations"
PYTHONPATH="$BACKEND_DIR" "$PYTHON_BIN" -m app.cli --env-file "$BACKEND_ENV_FILE" migrate

if [[ -f "$RUN_DIR/backend.pid" ]]; then
  existing_pid="$(cat "$RUN_DIR/backend.pid")"
  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" >/dev/null 2>&1; then
    echo "Backend already running with PID $existing_pid"
    exit 0
  fi
  rm -f "$RUN_DIR/backend.pid"
fi

lsof -iTCP:"$BACKEND_PORT" -sTCP:LISTEN -n -P | awk 'NR>1 {print $2}' | xargs -r kill >/dev/null 2>&1 || true

echo "Starting backend on $BACKEND_HOST:$BACKEND_PORT"
nohup sh -c "cd '$BACKEND_DIR' && PYTHONPATH='$BACKEND_DIR' '$PYTHON_BIN' -m uvicorn app.main:app --host '$BACKEND_HOST' --port '$BACKEND_PORT' --env-file '$BACKEND_ENV_FILE'" \
  > "$LOG_DIR/backend.log" 2>&1 &
echo $! > "$RUN_DIR/backend.pid"

echo "Running backend preflight"
PYTHONPATH="$BACKEND_DIR" "$PYTHON_BIN" -m app.cli \
  --env-file "$BACKEND_ENV_FILE" \
  preflight \
  --url "http://$BACKEND_HOST:$BACKEND_PORT/health" \
  --timeout-seconds 20 \
  --interval-seconds 1

echo "Backend PID: $(cat "$RUN_DIR/backend.pid")"
echo "Backend URL: http://$BACKEND_HOST:$BACKEND_PORT"
echo "Backend log: $LOG_DIR/backend.log"