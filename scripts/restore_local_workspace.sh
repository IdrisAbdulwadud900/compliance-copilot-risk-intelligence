#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-$BACKEND_DIR/.env}"
DEFAULT_DB_PATH="$BACKEND_DIR/data/copilot.db"
BACKUP_DIR="$BACKEND_DIR/data/backups"
RESTART_STACK=true
ASSUME_YES=false
DRY_RUN=false
DB_PATH_OVERRIDE=""
RESTORE_SOURCE=""

usage() {
  cat <<'EOF'
Usage: bash scripts/restore_local_workspace.sh [options]

Restore a local SQLite workspace backup into the active database path. The
current database is backed up before restore so the operation is reversible.

Options:
  --backup PATH      Backup file to restore from (defaults to newest *.db in backups/)
  --yes              Skip confirmation prompt
  --no-restart       Restore database without restarting local services
  --restart          Restart local services after restore (default)
  --env-file PATH    Load backend env vars from PATH
  --db-path PATH     Override the SQLite database path to restore into
  --dry-run          Print planned actions without changing anything
  --help             Show this help text
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup)
      RESTORE_SOURCE="$2"
      shift
      ;;
    --yes)
      ASSUME_YES=true
      ;;
    --no-restart)
      RESTART_STACK=false
      ;;
    --restart)
      RESTART_STACK=true
      ;;
    --env-file)
      BACKEND_ENV_FILE="$2"
      shift
      ;;
    --db-path)
      DB_PATH_OVERRIDE="$2"
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
  echo "Missing backend env file: $BACKEND_ENV_FILE" >&2
  exit 1
fi

resolve_db_path() {
  if [[ -n "$DB_PATH_OVERRIDE" ]]; then
    printf '%s\n' "$DB_PATH_OVERRIDE"
    return 0
  fi

  set -a
  # shellcheck disable=SC1090
  source "$BACKEND_ENV_FILE"
  set +a

  if [[ -n "${COMPLIANCE_DB_PATH:-}" ]]; then
    printf '%s\n' "$COMPLIANCE_DB_PATH"
    return 0
  fi

  if [[ -n "${COMPLIANCE_DATABASE_URL:-}" && "${COMPLIANCE_DATABASE_URL}" == sqlite:* ]]; then
    local sqlite_path="${COMPLIANCE_DATABASE_URL#sqlite:///}"
    if [[ -n "$sqlite_path" ]]; then
      printf '%s\n' "$sqlite_path"
      return 0
    fi
  fi

  printf '%s\n' "$DEFAULT_DB_PATH"
}

resolve_restore_source() {
  if [[ -n "$RESTORE_SOURCE" ]]; then
    printf '%s\n' "$RESTORE_SOURCE"
    return 0
  fi

  if [[ ! -d "$BACKUP_DIR" ]]; then
    return 1
  fi

  find "$BACKUP_DIR" -maxdepth 1 -type f -name '*.db' -print0 | xargs -0 ls -t 2>/dev/null | head -n 1
}

run_cmd() {
  if [[ "$DRY_RUN" == true ]]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

backup_file_if_present() {
  local source_path="$1"
  local suffix="$2"
  if [[ -f "$source_path" ]]; then
    run_cmd cp "$source_path" "$CURRENT_BACKUP_PREFIX$suffix"
  fi
}

remove_file_if_present() {
  local target_path="$1"
  if [[ -f "$target_path" ]]; then
    run_cmd rm -f "$target_path"
  fi
}

DB_PATH="$(resolve_db_path)"
if [[ "$DB_PATH" != /* ]]; then
  DB_PATH="$BACKEND_DIR/$DB_PATH"
fi
DB_DIR="$(dirname "$DB_PATH")"
DB_WAL="$DB_PATH-wal"
DB_SHM="$DB_PATH-shm"

RESTORE_FILE="$(resolve_restore_source || true)"
if [[ -z "$RESTORE_FILE" ]]; then
  echo "No backup file found to restore." >&2
  exit 1
fi
if [[ "$RESTORE_FILE" != /* ]]; then
  RESTORE_FILE="$ROOT_DIR/$RESTORE_FILE"
fi
if [[ ! -f "$RESTORE_FILE" ]]; then
  echo "Backup file not found: $RESTORE_FILE" >&2
  exit 1
fi

mkdir -p "$DB_DIR" "$BACKUP_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
CURRENT_BACKUP_PREFIX="$BACKUP_DIR/current_before_restore_$TIMESTAMP"

if [[ "$ASSUME_YES" != true ]]; then
  echo "About to restore local workspace database:"
  echo "  Restore from: $RESTORE_FILE"
  echo "  Restore into: $DB_PATH"
  echo "  Current backup prefix: $CURRENT_BACKUP_PREFIX"
  echo "  Restart stack: $RESTART_STACK"
  printf 'Continue? [y/N] '
  read -r reply
  if [[ ! "$reply" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
fi

echo "Restoring backup: $RESTORE_FILE"
echo "Target DB path: $DB_PATH"
echo "Current DB backup prefix: $CURRENT_BACKUP_PREFIX"

if [[ "$RESTART_STACK" == true ]]; then
  echo "Stopping local services"
  run_cmd bash "$ROOT_DIR/scripts/stop_local.sh"
fi

backup_file_if_present "$DB_PATH" ".db"
backup_file_if_present "$DB_WAL" ".db-wal"
backup_file_if_present "$DB_SHM" ".db-shm"

remove_file_if_present "$DB_WAL"
remove_file_if_present "$DB_SHM"
run_cmd cp "$RESTORE_FILE" "$DB_PATH"

echo "Local workspace database restored."

if [[ "$RESTART_STACK" == true ]]; then
  echo "Restarting local services"
  run_cmd bash "$ROOT_DIR/scripts/start_backend.sh"
  run_cmd bash "$ROOT_DIR/scripts/start_frontend.sh"
  run_cmd bash "$ROOT_DIR/scripts/status_local.sh"
fi

if [[ "$DRY_RUN" == true ]]; then
  echo "Dry run complete. No files were changed."
else
  echo "Restore complete. Previous active DB backup saved under: $BACKUP_DIR"
fi
