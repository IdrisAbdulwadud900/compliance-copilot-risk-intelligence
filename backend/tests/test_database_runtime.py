from app.storage.runtime import (
    _normalize_query,
    database_connection,
    database_healthcheck,
    resolve_database_runtime,
    sqlite_db_path,
    sqlite_healthcheck,
)


def test_runtime_defaults_to_sqlite_path(monkeypatch):
    monkeypatch.delenv("COMPLIANCE_DATABASE_URL", raising=False)
    monkeypatch.delenv("COMPLIANCE_DB_PATH", raising=False)

    runtime = resolve_database_runtime()
    assert runtime.backend == "sqlite"
    assert runtime.target.endswith("copilot.db")


def test_runtime_supports_sqlite_url(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_DATABASE_URL", "sqlite:////tmp/copilot-test.db")

    runtime = resolve_database_runtime()
    assert runtime.backend == "sqlite"
    assert runtime.target == "/tmp/copilot-test.db"
    assert sqlite_db_path() == "/tmp/copilot-test.db"


def test_runtime_marks_postgres_as_configured_but_not_implemented(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_DATABASE_URL", "postgresql://user:pass@localhost:5432/copilot")

    runtime = resolve_database_runtime()
    assert runtime.backend == "postgres"
    assert runtime.target == "postgresql://localhost:5432/copilot"

    try:
        sqlite_db_path()
    except RuntimeError as exc:
        assert "sqlite path helper supports sqlite only" in str(exc)
    else:
        raise AssertionError("Expected sqlite_db_path() to reject postgres runtime")


def test_sqlite_healthcheck_returns_false_for_unsupported_backend(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_DATABASE_URL", "postgresql://user:pass@localhost:5432/copilot")
    assert sqlite_healthcheck() is False


def test_database_connection_wrapper_supports_sqlite_queries(tmp_path, monkeypatch):
    db_path = str(tmp_path / "runtime_wrapper.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.delenv("COMPLIANCE_DATABASE_URL", raising=False)

    with database_connection() as conn:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY AUTOINCREMENT, value TEXT NOT NULL)")
        cursor = conn.execute("INSERT INTO sample (value) VALUES (?)", ("alpha",))
        conn.commit()
        row = conn.execute("SELECT id, value FROM sample WHERE id = ?", (cursor.lastrowid,)).fetchone()

    assert cursor.lastrowid is not None
    assert row["value"] == "alpha"


def test_normalize_query_for_postgres_rewrites_known_sqlite_patterns():
    assert _normalize_query("postgres", "SELECT * FROM users WHERE email = ?") == "SELECT * FROM users WHERE email = %s"
    assert "ON CONFLICT DO NOTHING" in _normalize_query(
        "postgres",
        "INSERT OR IGNORE INTO watchlist (tenant_id, chain, address) VALUES (?, ?, ?)",
    )
    assert "GREATEST(0, alert_count-1)" in _normalize_query(
        "postgres",
        "UPDATE incidents SET alert_count=MAX(0, alert_count-1), updated_at=? WHERE id=?",
    )


def test_database_healthcheck_false_for_unreachable_postgres(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_DATABASE_URL", "postgresql://user:pass@127.0.0.1:1/copilot")
    assert database_healthcheck() is False


def test_runtime_supports_standard_database_url_fallback(monkeypatch):
    monkeypatch.delenv("COMPLIANCE_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/copilot")

    runtime = resolve_database_runtime()

    assert runtime.backend == "postgres"
    assert runtime.target == "postgresql://localhost:5432/copilot"


def test_runtime_prefers_compliance_database_url_over_generic_fallback(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_DATABASE_URL", "sqlite:////tmp/primary.db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/copilot")

    runtime = resolve_database_runtime()

    assert runtime.backend == "sqlite"
    assert runtime.target == "/tmp/primary.db"