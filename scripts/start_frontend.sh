#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/logs"
FRONTEND_DIR="$ROOT_DIR/app"

FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

mkdir -p "$RUN_DIR" "$LOG_DIR"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to start the frontend" >&2
  exit 1
fi

if [[ -f "$RUN_DIR/frontend.pid" ]]; then
  existing_pid="$(cat "$RUN_DIR/frontend.pid")"
  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" >/dev/null 2>&1; then
    echo "Frontend already running with PID $existing_pid"
    exit 0
  fi
  rm -f "$RUN_DIR/frontend.pid"
fi

lsof -iTCP:"$FRONTEND_PORT" -sTCP:LISTEN -n -P | awk 'NR>1 {print $2}' | xargs -r kill >/dev/null 2>&1 || true

if [[ ! -d "$FRONTEND_DIR/.next" ]]; then
  echo "Building frontend production bundle..."
  (cd "$FRONTEND_DIR" && npm run build)
fi

echo "Starting frontend on $FRONTEND_HOST:$FRONTEND_PORT"
nohup sh -c "cd '$FRONTEND_DIR' && HOSTNAME='$FRONTEND_HOST' PORT='$FRONTEND_PORT' npm run start" \
  > "$LOG_DIR/frontend.log" 2>&1 &
echo $! > "$RUN_DIR/frontend.pid"

echo "Frontend PID: $(cat "$RUN_DIR/frontend.pid")"
echo "Frontend URL: http://$FRONTEND_HOST:$FRONTEND_PORT"
echo "Frontend log: $LOG_DIR/frontend.log"