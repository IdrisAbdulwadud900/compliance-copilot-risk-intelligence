from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_intelligence_watchlist_alerts_webhooks_cluster_flow(tmp_path, monkeypatch):
    db_path = str(tmp_path / "intel_flow.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        admin_token = _login(client, "owner@test.local", "OwnerPass123!")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Create webhook (admin-only)
        webhook_create = client.post(
            "/webhooks",
            headers=admin_headers,
            json={
                "url": "https://example.com/compliance-webhook",
                "events": ["alert.fired", "wallet.flagged", "watchlist.hit"],
            },
        )
        assert webhook_create.status_code == 200
        webhook_id = webhook_create.json()["id"]

        # Add watchlist entry
        watch_add = client.post(
            "/watchlist",
            headers=admin_headers,
            json={
                "chain": "bsc",
                "address": "0xaabbccdd11223344aabbccdd11223344aabbccdd",
                "label": "Suspect wallet",
                "alert_on_activity": True,
            },
        )
        assert watch_add.status_code == 200
        watch_id = watch_add.json()["id"]

        # Run intelligence to trigger watchlist hit alert
        intelligence = client.post(
            "/wallets/intelligence",
            headers=admin_headers,
            json={
                "chain": "bsc",
                "address": "0xaabbccdd11223344aabbccdd11223344aabbccdd",
                "txn_24h": 500,
                "volume_24h_usd": 900000,
                "sanctions_exposure_pct": 35,
                "mixer_exposure_pct": 25,
                "bridge_hops": 6,
            },
        )
        assert intelligence.status_code == 200
        intel_data = intelligence.json()
        assert intel_data["analysis_id"] > 0
        assert intel_data["address"] == "0xaabbccdd11223344aabbccdd11223344aabbccdd"
        assert isinstance(intel_data["fingerprints"], list)
        assert "recommended_action" in intel_data["narrative"]

        # Alerts should now include at least one item and unread_count >= 1
        alerts = client.get("/alert-events?limit=20", headers=admin_headers)
        assert alerts.status_code == 200
        alert_payload = alerts.json()
        assert isinstance(alert_payload["items"], list)
        assert alert_payload["unread_count"] >= 1
        hit = next((a for a in alert_payload["items"] if a["address"] == "0xaabbccdd11223344aabbccdd11223344aabbccdd"), None)
        assert hit is not None

        # Acknowledge alert
        ack = client.post(f"/alert-events/{hit['id']}/ack", headers=admin_headers)
        assert ack.status_code == 200

        # Cluster endpoint
        cluster = client.get("/wallets/0xaabbccdd11223344aabbccdd11223344aabbccdd/cluster?chain=bsc", headers=admin_headers)
        assert cluster.status_code == 200
        cluster_data = cluster.json()
        assert cluster_data["root_address"] == "0xaabbccdd11223344aabbccdd11223344aabbccdd"
        assert len(cluster_data["nodes"]) >= 1
        assert any(node["is_root"] for node in cluster_data["nodes"])

        # Cleanup paths
        webhook_delete = client.delete(f"/webhooks/{webhook_id}", headers=admin_headers)
        assert webhook_delete.status_code == 200

        watch_remove = client.delete(f"/watchlist/{watch_id}", headers=admin_headers)
        assert watch_remove.status_code == 200


def test_viewer_cannot_perform_restricted_intelligence_actions(tmp_path, monkeypatch):
    db_path = str(tmp_path / "intel_roles.db")
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
                "email": "viewer@test.local",
                "password": "ViewerPass123!",
                "role": "viewer",
            },
        )
        assert create_viewer.status_code == 200

        viewer_token = _login(client, "viewer@test.local", "ViewerPass123!")
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        intelligence = client.post(
            "/wallets/intelligence",
            headers=viewer_headers,
            json={
                "chain": "ethereum",
                "address": "0xabcdef1122334455aabbccddeeff001122334455",
                "txn_24h": 10,
                "volume_24h_usd": 1000,
                "sanctions_exposure_pct": 0,
                "mixer_exposure_pct": 0,
                "bridge_hops": 0,
            },
        )
        assert intelligence.status_code == 403

        watch_add = client.post(
            "/watchlist",
            headers=viewer_headers,
            json={
                "chain": "ethereum",
                "address": "0xabcdef1122334455aabbccddeeff001122334455",
                "label": "viewer attempt",
                "alert_on_activity": True,
            },
        )
        assert watch_add.status_code == 403

        webhooks = client.get("/webhooks", headers=viewer_headers)
        assert webhooks.status_code == 403
