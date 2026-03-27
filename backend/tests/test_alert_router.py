from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_alert_router_create_feed_ack_and_update_flow(tmp_path, monkeypatch):
    db_path = str(tmp_path / "alerts_flow.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        token = _login(client, "owner@test.local", "OwnerPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        first = client.post(
            "/alerts",
            headers=headers,
            json={
                "alert_type": "manual",
                "severity": "warning",
                "chain": "ethereum",
                "address": "0xALERTFLOW0001",
                "score": 64,
                "risk_level": "medium",
                "title": "Manual review needed",
                "body": "Potential anomalous outbound activity",
            },
        )
        assert first.status_code == 200
        first_id = first.json()["id"]

        second = client.post(
            "/alerts",
            headers=headers,
            json={
                "alert_type": "manual",
                "severity": "critical",
                "chain": "bsc",
                "address": "bc1alertflow0002",
                "score": 92,
                "risk_level": "critical",
                "title": "Escalate investigation",
                "body": "High-risk manual escalation",
            },
        )
        assert second.status_code == 200
        second_id = second.json()["id"]

        listed = client.get("/alerts?limit=10", headers=headers)
        assert listed.status_code == 200
        listed_payload = listed.json()
        assert listed_payload["unread_count"] >= 2
        assert any(item["id"] == first_id for item in listed_payload["items"])
        assert any(item["id"] == second_id for item in listed_payload["items"])

        feed = client.get("/alerts/feed?since_id=0&limit=10", headers=headers)
        assert feed.status_code == 200
        assert feed.json()["last_id"] >= second_id

        incident = client.post(
            "/incidents",
            headers=headers,
            json={
                "title": "Alert triage incident",
                "description": "Aggregate linked manual alerts",
                "severity": "warning",
                "alert_ids": [],
            },
        )
        assert incident.status_code == 200
        incident_id = incident.json()["id"]

        updated = client.patch(
            f"/alerts/{first_id}",
            headers=headers,
            json={"resolved": True, "incident_id": incident_id},
        )
        assert updated.status_code == 200
        assert updated.json() == {"updated": True, "alert_id": first_id}

        incident_filtered = client.get(f"/alerts?incident_id={incident_id}", headers=headers)
        assert incident_filtered.status_code == 200
        assert any(item["id"] == first_id for item in incident_filtered.json()["items"])

        event_list_before_ack = client.get("/alert-events?limit=10", headers=headers)
        assert event_list_before_ack.status_code == 200
        assert any(item["id"] == second_id for item in event_list_before_ack.json()["items"])

        ack_event = client.post(f"/alert-events/{second_id}/ack", headers=headers)
        assert ack_event.status_code == 200
        assert ack_event.json()["acknowledged"] is True

        third = client.post(
            "/alerts",
            headers=headers,
            json={
                "alert_type": "manual",
                "severity": "warning",
                "chain": "ethereum",
                "address": "0xALERTFLOW0003",
                "score": 55,
                "risk_level": "medium",
                "title": "Secondary follow-up",
                "body": "Validate direct alert ack endpoint",
            },
        )
        assert third.status_code == 200
        third_id = third.json()["id"]

        ack_single = client.post(f"/alerts/{third_id}/ack", headers=headers)
        assert ack_single.status_code == 200
        assert ack_single.json()["alert_id"] == third_id

        fourth = client.post(
            "/alerts",
            headers=headers,
            json={
                "alert_type": "manual",
                "severity": "warning",
                "chain": "bsc",
                "address": "0xALERTFLOW0004",
                "score": 48,
                "risk_level": "medium",
                "title": "Ack all validation",
                "body": "Leave this unread for ack-all coverage",
            },
        )
        assert fourth.status_code == 200

        ack_all = client.post("/alerts/ack-all", headers=headers)
        assert ack_all.status_code == 200
        assert ack_all.json()["acked"] >= 1

        event_list = client.get("/alert-events?unacked_only=true", headers=headers)
        assert event_list.status_code == 200
        assert event_list.json()["unread_count"] == 0


def test_alert_router_blocks_viewer_mutations(tmp_path, monkeypatch):
    db_path = str(tmp_path / "alerts_roles.db")
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
                "email": "viewer-alerts@test.local",
                "password": "ViewerPass123!",
                "role": "viewer",
            },
        )
        assert create_viewer.status_code == 200

        created_alert = client.post(
            "/alerts",
            headers=admin_headers,
            json={
                "alert_type": "manual",
                "severity": "warning",
                "chain": "ethereum",
                "address": "0xVIEWERBLOCK0001",
                "score": 40,
                "risk_level": "medium",
                "title": "Viewer restriction test",
                "body": "Ensure viewers cannot mutate alerts",
            },
        )
        assert created_alert.status_code == 200
        alert_id = created_alert.json()["id"]

        viewer_token = _login(client, "viewer-alerts@test.local", "ViewerPass123!")
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        viewer_create = client.post(
            "/alerts",
            headers=viewer_headers,
            json={
                "alert_type": "manual",
                "severity": "warning",
                "chain": "ethereum",
                "address": "0xVIEWERBLOCK0002",
                "score": 10,
                "risk_level": "low",
                "title": "Forbidden",
                "body": "This should not be allowed",
            },
        )
        assert viewer_create.status_code == 403

        viewer_update = client.patch(
            f"/alerts/{alert_id}",
            headers=viewer_headers,
            json={"resolved": True},
        )
        assert viewer_update.status_code == 403
