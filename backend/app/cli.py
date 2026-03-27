from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from dotenv import load_dotenv

from app.migrations import apply_migrations, migration_status_summary
from app.storage.runtime import resolve_database_runtime


def _load_env_file(env_file: str | None) -> None:
    if not env_file:
        return
    env_path = Path(env_file)
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found: {env_file}")
    load_dotenv(env_path, override=False)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument("--env-file", help="Optional dotenv file to load before running the command")

    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate_parser = subparsers.add_parser("migrate", help="Apply all pending sqlite schema migrations")
    migrate_parser.add_argument("--db-path", help="Override the sqlite database file path")

    status_parser = subparsers.add_parser("status", help="Show applied and pending migration versions")
    status_parser.add_argument("--db-path", help="Override the sqlite database file path")

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="Apply migrations, show schema status, and verify the service health endpoint",
    )
    preflight_parser.add_argument("--db-path", help="Override the sqlite database file path")
    preflight_parser.add_argument("--url", default="http://127.0.0.1:8000/health", help="Health endpoint URL")
    preflight_parser.add_argument("--timeout-seconds", type=float, default=15.0, help="Total time budget for polling")
    preflight_parser.add_argument("--interval-seconds", type=float, default=1.0, help="Delay between retries")

    health_parser = subparsers.add_parser("health", help="Poll a health endpoint until it reports status ok")
    health_parser.add_argument("--url", default="http://127.0.0.1:8000/health", help="Health endpoint URL")
    health_parser.add_argument("--timeout-seconds", type=float, default=15.0, help="Total time budget for polling")
    health_parser.add_argument("--interval-seconds", type=float, default=1.0, help="Delay between retries")
    return parser


def _status_lines(db_path: str | None) -> list[str]:
    runtime = resolve_database_runtime()
    migration_status = migration_status_summary(db_path)
    return [
        f"backend={runtime.backend}",
        f"target={runtime.target}",
        f"applied={','.join(str(version) for version in migration_status['applied_versions']) or 'none'}",
        f"pending={','.join(str(version) for version in migration_status['pending_versions']) or 'none'}",
    ]


def _health_lines(url: str, timeout_seconds: float, interval_seconds: float) -> list[str]:
    deadline = time.monotonic() + max(timeout_seconds, 0.1)
    last_error = "unavailable"

    while time.monotonic() <= deadline:
        try:
            with urlopen(url, timeout=max(interval_seconds, 0.1)) as response:
                body = response.read().decode("utf-8")
            payload = json.loads(body)
            status_value = str(payload.get("status", "unknown"))
            if status_value == "ok":
                return [
                    f"health_url={url}",
                    f"health_status={status_value}",
                    f"service={payload.get('service', 'unknown')}",
                ]
            last_error = f"unexpected status={status_value}"
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)

        if time.monotonic() + max(interval_seconds, 0.0) > deadline:
            break
        time.sleep(max(interval_seconds, 0.0))

    raise RuntimeError(f"Health check failed for {url}: {last_error}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        _load_env_file(args.env_file)

        if args.command == "migrate":
            apply_migrations(args.db_path)
            for line in _status_lines(args.db_path):
                print(line)
            print("result=migrated")
            return 0

        if args.command == "status":
            for line in _status_lines(args.db_path):
                print(line)
            return 0

        if args.command == "health":
            for line in _health_lines(args.url, args.timeout_seconds, args.interval_seconds):
                print(line)
            return 0

        if args.command == "preflight":
            apply_migrations(args.db_path)
            for line in _status_lines(args.db_path):
                print(line)
            for line in _health_lines(args.url, args.timeout_seconds, args.interval_seconds):
                print(line)
            print("result=preflight_ok")
            return 0
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"error={exc}")
        return 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())