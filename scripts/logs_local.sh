#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"

SERVICE="${1:-all}"
LINES="${LINES:-40}"

show_log() {
  local label="$1"
  local file="$2"

  echo "== $label =="
  if [[ -f "$file" ]]; then
    tail -n "$LINES" "$file"
  else
    echo "missing log: $file"
  fi
}

case "$SERVICE" in
  backend)
    show_log backend "$LOG_DIR/backend.log"
    ;;
  frontend)
    show_log frontend "$LOG_DIR/frontend.log"
    ;;
  all)
    show_log backend "$LOG_DIR/backend.log"
    echo
    show_log frontend "$LOG_DIR/frontend.log"
    ;;
  *)
    echo "Usage: bash scripts/logs_local.sh [backend|frontend|all]" >&2
    exit 1
    ;;
esac