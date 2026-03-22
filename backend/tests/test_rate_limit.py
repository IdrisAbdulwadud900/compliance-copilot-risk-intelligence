from fastapi.testclient import TestClient

from app.main import app
from app.rate_limit import reset_rate_limits


def test_auth_login_rate_limit(tmp_path, monkeypatch):
    db_path = str(tmp_path / "ratelimit.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner3@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-c")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")
    monkeypatch.setenv("COMPLIANCE_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("COMPLIANCE_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("COMPLIANCE_RATE_LIMIT_AUTH_MAX_REQUESTS", "2")

    reset_rate_limits()
    with TestClient(app) as client:
        for _ in range(2):
            response = client.post(
                "/auth/login",
                headers={"x-forwarded-for": "198.51.100.20"},
                json={"email": "owner3@test.local", "password": "wrong-pass"},
            )
            assert response.status_code == 401

        blocked = client.post(
            "/auth/login",
            headers={"x-forwarded-for": "198.51.100.20"},
            json={"email": "owner3@test.local", "password": "wrong-pass"},
        )
        assert blocked.status_code == 429


def test_invite_status_rate_limit(tmp_path, monkeypatch):
    db_path = str(tmp_path / "ratelimit_invite.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner4@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-d")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")
    monkeypatch.setenv("COMPLIANCE_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("COMPLIANCE_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("COMPLIANCE_RATE_LIMIT_INVITE_STATUS_MAX_REQUESTS", "2")

    reset_rate_limits()
    with TestClient(app) as client:
        for _ in range(2):
            response = client.get(
                "/auth/invite-status?token=test-token-does-not-exist",
                headers={"x-forwarded-for": "203.0.113.8"},
            )
            assert response.status_code == 200

        blocked = client.get(
            "/auth/invite-status?token=test-token-does-not-exist",
            headers={"x-forwarded-for": "203.0.113.8"},
        )
        assert blocked.status_code == 429
