from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_watchlist_router_add_list_remove_and_duplicate(tmp_path, monkeypatch):
    db_path = str(tmp_path / "watchlist_flow.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        token = _login(client, "owner@test.local", "OwnerPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post(
            "/watchlist",
            headers=headers,
            json={
                "chain": "ethereum",
                "address": "0xWATCHLIST0001",
                "label": "Sanctions review",
                "alert_on_activity": True,
            },
        )
        assert created.status_code == 200
        entry_id = created.json()["id"]

        listed = client.get("/watchlist", headers=headers)
        assert listed.status_code == 200
        assert any(item["id"] == entry_id for item in listed.json()["items"])

        duplicate = client.post(
            "/watchlist",
            headers=headers,
            json={
                "chain": "ethereum",
                "address": "0xWATCHLIST0001",
                "label": "Sanctions review",
                "alert_on_activity": True,
            },
        )
        assert duplicate.status_code == 409

        removed = client.delete(f"/watchlist/{entry_id}", headers=headers)
        assert removed.status_code == 200
        assert removed.json()["removed"] is True


def test_watchlist_router_blocks_viewer_mutations(tmp_path, monkeypatch):
    db_path = str(tmp_path / "watchlist_roles.db")
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
            json={
                "email": "viewer-watchlist@test.local",
                "password": "ViewerPass123!",
                "role": "viewer",
            },
        )
        assert create_viewer.status_code == 200

        created = client.post(
            "/watchlist",
            headers=admin_headers,
            json={
                "chain": "bsc",
                "address": "0xWATCHLIST0002",
                "label": "Viewer guard",
                "alert_on_activity": True,
            },
        )
        assert created.status_code == 200
        entry_id = created.json()["id"]

        viewer_token = _login(client, "viewer-watchlist@test.local", "ViewerPass123!")
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        viewer_list = client.get("/watchlist", headers=viewer_headers)
        assert viewer_list.status_code == 200

        viewer_create = client.post(
            "/watchlist",
            headers=viewer_headers,
            json={
                "chain": "ethereum",
                "address": "0xWATCHLIST0003",
                "label": "Forbidden",
                "alert_on_activity": True,
            },
        )
        assert viewer_create.status_code == 403

        viewer_delete = client.delete(f"/watchlist/{entry_id}", headers=viewer_headers)
        assert viewer_delete.status_code == 403