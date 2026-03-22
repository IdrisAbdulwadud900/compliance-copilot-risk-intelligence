from fastapi.testclient import TestClient

from app.main import app


def test_list_and_revoke_invite(tmp_path, monkeypatch):
    db_path = str(tmp_path / "revoke.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner2@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-b")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        admin_login = client.post(
            "/auth/login",
            json={"email": "owner2@test.local", "password": "OwnerPass123!"},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]

        invite = client.post(
            "/users/invite",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": "viewer2@test.local", "role": "viewer"},
        )
        assert invite.status_code == 200
        token = invite.json()["token"]

        public_status_active = client.get(f"/auth/invite-status?token={token}")
        assert public_status_active.status_code == 200
        assert public_status_active.json()["status"] == "active"

        listed = client.get(
            "/users/invites?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert any(item["token"] == token and item["status"] == "active" for item in items)

        revoked = client.delete(
            f"/users/invites/{token}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert revoked.status_code == 200
        assert revoked.json()["revoked"] is True

        public_status_revoked = client.get(f"/auth/invite-status?token={token}")
        assert public_status_revoked.status_code == 200
        assert public_status_revoked.json()["status"] == "revoked"

        listed_again = client.get(
            "/users/invites?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert listed_again.status_code == 200
        items_again = listed_again.json()["items"]
        assert any(item["token"] == token and item["status"] == "revoked" for item in items_again)

        accept = client.post(
            "/auth/accept-invite",
            json={"token": token, "password": "ViewerPass123!"},
        )
        assert accept.status_code == 400
