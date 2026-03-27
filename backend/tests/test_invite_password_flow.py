from fastapi.testclient import TestClient

from app.main import app


def test_invite_accept_and_change_password_flow(tmp_path, monkeypatch):
    db_path = str(tmp_path / "flow.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        admin_login = client.post(
            "/auth/login",
            json={"email": "owner@test.local", "password": "OwnerPass123!"},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]

        invite = client.post(
            "/users/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": "analyst@test.local", "role": "analyst"},
        )
        assert invite.status_code == 200
        token = invite.json()["token"]

        accept = client.post(
            "/auth/accept-invite",
            json={"token": token, "password": "AnalystPass123!"},
        )
        assert accept.status_code == 200
        analyst_token = accept.json()["access_token"]

        change_password = client.post(
            "/auth/change-password",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={
                "current_password": "AnalystPass123!",
                "new_password": "AnalystPass456!",
            },
        )
        assert change_password.status_code == 200


def test_invite_accept_rejects_short_password(tmp_path, monkeypatch):
    db_path = str(tmp_path / "invite_short_password.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        admin_login = client.post(
            "/auth/login",
            json={"email": "owner@test.local", "password": "OwnerPass123!"},
        )
        admin_token = admin_login.json()["access_token"]

        invite = client.post(
            "/users/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": "analyst-short@test.local", "role": "analyst"},
        )
        token = invite.json()["token"]

        accept = client.post(
            "/auth/accept-invite",
            json={"token": token, "password": "Short123!"},
        )

    assert accept.status_code == 422
