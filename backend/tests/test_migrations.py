import sqlite3

from app.db import init_db
from app.migrations import available_migration_versions, get_applied_migration_versions


def test_init_db_applies_all_migrations_on_fresh_database(tmp_path):
    db_path = str(tmp_path / "fresh_migrations.db")

    init_db(db_path)

    applied = get_applied_migration_versions(db_path)
    assert applied == available_migration_versions()

    with sqlite3.connect(db_path) as conn:
        migration_rows = conn.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall()
        assert len(migration_rows) == len(available_migration_versions())

        analysis_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(analyses)").fetchall()
        }
        assert {"tenant_id", "chain", "tags"}.issubset(analysis_columns)

        alert_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(alert_events)").fetchall()
        }
        assert {"alert_type", "severity", "prev_score", "acknowledged_at", "resolved_at", "incident_id"}.issubset(alert_columns)


def test_init_db_upgrades_legacy_database_schema(tmp_path):
    db_path = str(tmp_path / "legacy_upgrade.db")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                address TEXT NOT NULL,
                txn_24h INTEGER NOT NULL,
                volume_24h_usd REAL NOT NULL,
                sanctions_exposure_pct REAL NOT NULL,
                mixer_exposure_pct REAL NOT NULL,
                bridge_hops INTEGER NOT NULL,
                score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                explanation TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE alert_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                trigger TEXT NOT NULL,
                chain TEXT NOT NULL,
                address TEXT NOT NULL,
                score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()

    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        analyses_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(analyses)").fetchall()
        }
        assert {"tenant_id", "chain", "tags"}.issubset(analyses_columns)

        users_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        assert "role" in users_columns

        invites_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(invites)").fetchall()
        }
        assert "revoked_at" in invites_columns

        alert_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(alert_events)").fetchall()
        }
        assert {"alert_type", "severity", "prev_score", "acknowledged_at", "resolved_at", "incident_id"}.issubset(alert_columns)

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {"incidents", "webhooks", "cases", "case_events", "case_notes", "case_entities", "case_attachments", "schema_migrations"}.issubset(tables)

    assert get_applied_migration_versions(db_path) == available_migration_versions()
