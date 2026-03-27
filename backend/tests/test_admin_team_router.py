from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_team_router_user_and_invite_flow(tmp_path, monkeypatch):
    db_path = str(tmp_path / "admin_team.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        token = _login(client, "owner@test.local", "OwnerPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        users_before = client.get("/users", headers=headers)
        assert users_before.status_code == 200

        created_user = client.post(
            "/users",
            headers=headers,
            json={"email": "analyst1@test.local", "password": "AnalystPass123!", "role": "analyst"},
        )
        assert created_user.status_code == 200
        assert created_user.json()["email"] == "analyst1@test.local"

        invite = client.post(
            "/users/invite",
            headers=headers,
            json={"email": "invitee@test.local", "role": "viewer"},
        )
        assert invite.status_code == 200
        token_value = invite.json()["token"]

        invite_list = client.get("/users/invites", headers=headers)
        assert invite_list.status_code == 200
        assert any(item["token"] == token_value for item in invite_list.json()["items"])

        revoke = client.delete(f"/users/invites/{token_value}", headers=headers)
        assert revoke.status_code == 200
        assert revoke.json()["revoked"] is True


def test_admin_team_router_blocks_non_admin(tmp_path, monkeypatch):
    db_path = str(tmp_path / "admin_team_roles.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        admin_token = _login(client, "owner@test.local", "OwnerPass123!")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        create_viewer = client.post(
            "/users",
            headers=admin_headers,
            json={"email": "viewer2@test.local", "password": "ViewerPass123!", "role": "viewer"},
        )
        assert create_viewer.status_code == 200

        viewer_token = _login(client, "viewer2@test.local", "ViewerPass123!")
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        assert client.get("/users", headers=viewer_headers).status_code == 403
        assert client.get("/users/invites", headers=viewer_headers).status_code == 403
        assert client.get("/audit-logs", headers=viewer_headers).status_code == 403
