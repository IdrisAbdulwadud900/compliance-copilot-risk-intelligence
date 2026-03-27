from fastapi.testclient import TestClient

from app.auth import get_current_principal
from app.config import config_warnings
from app.db import authenticate_user, init_db
from app.main import app


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_api_key_role_defaults_to_viewer(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_API_KEYS", "service-key:tenant-z")
    principal = get_current_principal(authorization="", x_api_key="service-key")
    assert principal == ("tenant-z", "viewer", "api-key-user")


def test_default_admin_is_not_seeded_without_explicit_env(tmp_path, monkeypatch):
    db_path = str(tmp_path / "no_seed.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.delenv("COMPLIANCE_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("COMPLIANCE_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("COMPLIANCE_ADMIN_TENANT", raising=False)

    init_db(db_path)

    assert authenticate_user("founder@demo.local", "ChangeMe123!", db_path) is None


def test_insecure_preview_admin_requires_preview_bootstrap_flag(tmp_path, monkeypatch):
    db_path = str(tmp_path / "preview_seed.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "founder@demo.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "ChangeMe123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "demo-tenant")
    monkeypatch.delenv("COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP", raising=False)

    init_db(db_path)

    assert authenticate_user("founder@demo.local", "ChangeMe123!", db_path) is None


def test_insecure_preview_admin_can_seed_with_preview_bootstrap_flag(tmp_path, monkeypatch):
    db_path = str(tmp_path / "preview_seed_enabled.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "founder@demo.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "ChangeMe123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "demo-tenant")
    monkeypatch.setenv("COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP", "true")

    init_db(db_path)

    assert authenticate_user("founder@demo.local", "ChangeMe123!", db_path) == (
        "founder@demo.local",
        "demo-tenant",
        "admin",
    )


def test_ready_endpoint_reports_warnings(tmp_path, monkeypatch):
    db_path = str(tmp_path / "ready.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")
    monkeypatch.delenv("COMPLIANCE_API_KEYS", raising=False)

    with TestClient(app) as client:
        response = client.get("/ready")
        assert response.status_code == 200
        payload = response.json()
        assert payload["checks"]["database"] == "ok"
        assert payload["checks"]["persistence"] == "ok"
        assert payload["migrations"]["up_to_date"] is True
        assert "warnings" in payload
        assert payload["status"] == "ok"
        assert payload["recommended_action"] == "none"


def test_health_sets_request_id_header(tmp_path, monkeypatch):
    db_path = str(tmp_path / "request_id.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)

    with TestClient(app) as client:
        response = client.get("/health", headers={"x-request-id": "req-test-123"})
        assert response.status_code == 200
        assert response.headers["x-request-id"] == "req-test-123"


def test_root_endpoint_returns_service_metadata(tmp_path, monkeypatch):
    db_path = str(tmp_path / "root.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "crypto-compliance-copilot-api"
    assert payload["health_url"] == "/health"
    assert payload["ready_url"] == "/ready"
    assert payload["docs_url"] == "/docs"
    assert payload["database"]["backend"] == "sqlite"
    assert payload["database"]["persistence"] == "local-disk"


def test_private_webhook_url_rejected(tmp_path, monkeypatch):
    db_path = str(tmp_path / "webhook_guard.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        token = _login(client, "owner@test.local", "OwnerPass123!")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            "/webhooks",
            headers=headers,
            json={
                "url": "http://127.0.0.1/internal-webhook",
                "events": ["alert.fired"],
            },
        )
        assert response.status_code == 400
        assert "private" in response.json()["detail"] or "localhost" in response.json()["detail"]


def test_production_sqlite_emits_warning(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_ENV", "production")
    monkeypatch.delenv("COMPLIANCE_DATABASE_URL", raising=False)
    monkeypatch.delenv("COMPLIANCE_DB_PATH", raising=False)

    warnings = config_warnings()
    assert "sqlite_in_production" in warnings


def test_ephemeral_sqlite_emits_warning_in_production(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_ENV", "production")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", "/tmp/copilot.db")

    warnings = config_warnings()
    assert "sqlite_in_production" in warnings
    assert "ephemeral_sqlite_storage" in warnings


def test_ready_endpoint_degrades_for_ephemeral_sqlite_in_production(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_ENV", "production")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", "/tmp/copilot.db")
    monkeypatch.setenv("COMPLIANCE_JWT_SECRET", "prod-secret-value")
    monkeypatch.setenv("COMPLIANCE_WEBHOOK_SECRET", "prod-webhook-secret")
    monkeypatch.setenv("COMPLIANCE_ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.delenv("COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP", raising=False)
    monkeypatch.delenv("COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS", raising=False)
    monkeypatch.delenv("COMPLIANCE_ADMIN_PASSWORD", raising=False)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["config"] == "warning"
    assert payload["checks"]["persistence"] == "warning"
    assert payload["database"]["persistence"] == "ephemeral"
    assert "sqlite_in_production" in payload["warnings"]
    assert "ephemeral_sqlite_storage" in payload["warnings"]
    assert "COMPLIANCE_DATABASE_URL" in payload["recommended_action"]


def test_preview_bootstrap_warning_is_explicit(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP", "true")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "ChangeMe123!")

    warnings = config_warnings()

    assert "preview_bootstrap_enabled" in warnings
    assert "preview_default_admin_enabled" in warnings
    assert "default_admin_password_configured" not in warnings


def test_health_reports_database_runtime(tmp_path, monkeypatch):
    db_path = str(tmp_path / "health_runtime.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["database"]["backend"] == "sqlite"
        assert payload["database"]["target"]
        assert payload["database"]["persistence"] == "local-disk"
        assert payload["migrations"]["current_version"] >= 1
        assert payload["migrations"]["up_to_date"] is True
