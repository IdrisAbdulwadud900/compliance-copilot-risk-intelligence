from fastapi.testclient import TestClient

from app.auth import get_current_principal, get_current_tenant, login_and_issue_token
from app.db import init_db
from app.main import app


def test_login_and_token_tenant_resolution(tmp_path, monkeypatch):
    db_path = str(tmp_path / "auth.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "StrongPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-x")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "analyst")
    monkeypatch.setenv("COMPLIANCE_JWT_SECRET", "unit-test-secret")

    init_db()

    token_tuple = login_and_issue_token("owner@test.local", "StrongPass123!")
    assert token_tuple is not None
    token, email, tenant_id, role = token_tuple
    assert email == "owner@test.local"
    assert tenant_id == "tenant-x"
    assert role == "analyst"

    resolved = get_current_tenant(authorization=f"Bearer {token}", x_api_key="")
    assert resolved == "tenant-x"

    principal = get_current_principal(authorization=f"Bearer {token}", x_api_key="")
    assert principal == ("tenant-x", "analyst", "owner@test.local")


def test_preview_oauth_signup_disabled_by_default(monkeypatch):
    monkeypatch.delenv("COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS", raising=False)

    with TestClient(app) as client:
        response = client.post(
            "/auth/signup/oauth",
            json={"provider": "google", "email": "analyst@example.com"},
        )

    assert response.status_code == 404
    assert "disabled" in response.json()["detail"].lower()


def test_preview_phone_signup_enabled_with_flag(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS", "true")

    with TestClient(app) as client:
        response = client.post(
            "/auth/signup/phone/start",
            json={"phone": "+1 555 010 1000"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["code_hint"].startswith("demo-")


def test_setup_status_reports_empty_workspace(tmp_path, monkeypatch):
    db_path = str(tmp_path / "setup_status_empty.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.delenv("COMPLIANCE_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("COMPLIANCE_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("COMPLIANCE_ADMIN_TENANT", raising=False)
    monkeypatch.delenv("COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP", raising=False)

    with TestClient(app) as client:
        response = client.get("/auth/setup-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "status": "ok",
        "workspace_ready": False,
        "user_count": 0,
        "first_signup_becomes_admin": True,
    }


def test_setup_status_reports_ready_workspace(tmp_path, monkeypatch):
    db_path = str(tmp_path / "setup_status_ready.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.delenv("COMPLIANCE_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("COMPLIANCE_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("COMPLIANCE_ADMIN_TENANT", raising=False)
    monkeypatch.delenv("COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP", raising=False)

    with TestClient(app) as client:
        signup = client.post(
            "/auth/signup",
            json={"email": "owner@company.com", "password": "StrongPass123!", "role": "analyst"},
        )
        response = client.get("/auth/setup-status")

    assert signup.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace_ready"] is True
    assert payload["user_count"] == 1
    assert payload["first_signup_becomes_admin"] is False
def test_first_signup_becomes_admin(tmp_path, monkeypatch):
    db_path = str(tmp_path / "first_signup.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.delenv("COMPLIANCE_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("COMPLIANCE_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("COMPLIANCE_ADMIN_TENANT", raising=False)
    monkeypatch.delenv("COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP", raising=False)
    monkeypatch.setenv("COMPLIANCE_JWT_SECRET", "unit-test-secret")

    with TestClient(app) as client:
        response = client.post(
            "/auth/signup",
            json={"email": "owner@company.com", "password": "StrongPass123!", "role": "analyst"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "owner@company.com"
    assert payload["role"] == "admin"


def test_second_signup_keeps_requested_role(tmp_path, monkeypatch):
    db_path = str(tmp_path / "second_signup.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.delenv("COMPLIANCE_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("COMPLIANCE_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("COMPLIANCE_ADMIN_TENANT", raising=False)
    monkeypatch.delenv("COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP", raising=False)
    monkeypatch.setenv("COMPLIANCE_JWT_SECRET", "unit-test-secret")

    with TestClient(app) as client:
        first = client.post(
            "/auth/signup",
            json={"email": "owner@company.com", "password": "StrongPass123!", "role": "analyst"},
        )
        second = client.post(
            "/auth/signup",
            json={"email": "analyst@company.com", "password": "AnalystPass123!", "role": "analyst"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["role"] == "analyst"
