from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class DatabaseRuntime:
    backend: str
    target: str


class DatabaseCursor:
    def __init__(self, backend: str, cursor: Any, connection: "DatabaseConnection") -> None:
        self.backend = backend
        self._cursor = cursor
        self._connection = connection

    @property
    def rowcount(self) -> int:
        return getattr(self._cursor, "rowcount", 0)

    @property
    def lastrowid(self) -> Optional[int]:
        if self.backend == "sqlite":
            return getattr(self._cursor, "lastrowid", None)
        return self._connection.last_insert_id

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class DatabaseConnection:
    def __init__(self, backend: str, raw_connection: Any) -> None:
        self.backend = backend
        self._raw_connection = raw_connection
        self._last_insert_id: Optional[int] = None

    @property
    def last_insert_id(self) -> Optional[int]:
        return self._last_insert_id

    def __enter__(self) -> "DatabaseConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None:
            try:
                self.rollback()
            except Exception:
                pass
        self.close()

    def execute(self, query: str, params: Iterable[Any] = ()):  # noqa: ANN201
        normalized_query = _normalize_query(self.backend, query)
        normalized_params = tuple(params)

        if self.backend == "sqlite":
            cursor = self._raw_connection.execute(normalized_query, normalized_params)
            return DatabaseCursor(self.backend, cursor, self)

        from psycopg.rows import dict_row  # type: ignore[import-not-found]

        cursor = self._raw_connection.cursor(row_factory=dict_row)
        cursor.execute(normalized_query, normalized_params)
        self._capture_postgres_last_insert_id(normalized_query, cursor)
        return DatabaseCursor(self.backend, cursor, self)

    def commit(self) -> None:
        self._raw_connection.commit()

    def rollback(self) -> None:
        self._raw_connection.rollback()

    def close(self) -> None:
        self._raw_connection.close()

    def _capture_postgres_last_insert_id(self, query: str, cursor: Any) -> None:
        self._last_insert_id = None
        if not query.lstrip().upper().startswith("INSERT") or cursor.rowcount <= 0:
            return
        try:
            with self._raw_connection.cursor() as id_cursor:
                id_cursor.execute("SELECT LASTVAL()")
                row = id_cursor.fetchone()
        except Exception:
            self._last_insert_id = None
            return

        if not row:
            return
        value = row[0] if isinstance(row, tuple) else next(iter(row.values()))
        self._last_insert_id = int(value)


def database_url() -> str:
    return os.getenv("COMPLIANCE_DATABASE_URL", "").strip()


def _redact_postgres_target(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "postgres"
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    path = parsed.path or ""
    scheme = parsed.scheme or "postgresql"
    return f"{scheme}://{netloc}{path}"


def resolve_database_runtime() -> DatabaseRuntime:
    url = database_url()
    normalized = url.lower()
    if normalized.startswith(("postgres://", "postgresql://")):
        return DatabaseRuntime(backend="postgres", target=_redact_postgres_target(url))
    if normalized.startswith("sqlite:///"):
        return DatabaseRuntime(backend="sqlite", target=url.replace("sqlite:///", "", 1))
    if normalized == "sqlite:///:memory:":
        return DatabaseRuntime(backend="sqlite", target=":memory:")
    if url:
        return DatabaseRuntime(backend="unknown", target=url)

    configured = os.getenv("COMPLIANCE_DB_PATH", "").strip()
    if configured:
        return DatabaseRuntime(backend="sqlite", target=configured)

    base_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return DatabaseRuntime(backend="sqlite", target=str(data_dir / "copilot.db"))


def sqlite_db_path(db_path: Optional[str] = None) -> str:
    if db_path:
        return db_path

    runtime = resolve_database_runtime()
    if runtime.backend != "sqlite":
        raise RuntimeError(
            "Current sqlite path helper supports sqlite only; "
            f"configured backend is {runtime.backend}"
        )
    return runtime.target


def _postgres_connect():
    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Postgres backend requires psycopg. Install backend dependencies first."
        ) from exc

    return psycopg.connect(database_url())


def _replace_qmark_placeholders(query: str) -> str:
    parts = query.split("?")
    if len(parts) == 1:
        return query
    return "%s".join(parts)


def _normalize_query(backend: str, query: str) -> str:
    normalized = query
    if backend != "postgres":
        return normalized

    normalized = normalized.replace("INSERT OR IGNORE INTO", "INSERT INTO")
    if "INSERT INTO watchlist" in normalized and "ON CONFLICT DO NOTHING" not in normalized:
        normalized = normalized.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    normalized = normalized.replace("MAX(0, alert_count-1)", "GREATEST(0, alert_count-1)")
    return _replace_qmark_placeholders(normalized)


def database_connection(db_path: Optional[str] = None) -> DatabaseConnection:
    runtime = resolve_database_runtime()
    if runtime.backend == "sqlite":
        raw_connection = sqlite3.connect(sqlite_db_path(db_path))
        raw_connection.row_factory = sqlite3.Row
        return DatabaseConnection("sqlite", raw_connection)
    if runtime.backend == "postgres":
        if db_path:
            raise RuntimeError("db_path override is not supported for postgres runtime")
        return DatabaseConnection("postgres", _postgres_connect())
    raise RuntimeError(f"Unsupported database backend: {runtime.backend}")


def sqlite_connection(db_path: Optional[str] = None) -> DatabaseConnection:
    return database_connection(db_path)


def database_healthcheck(db_path: Optional[str] = None) -> bool:
    try:
        with database_connection(db_path) as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False


def sqlite_healthcheck(db_path: Optional[str] = None) -> bool:
    return database_healthcheck(db_path)