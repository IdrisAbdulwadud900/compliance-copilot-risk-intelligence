from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_incident_router_crud_and_alert_link_flow(tmp_path, monkeypatch):
    db_path = str(tmp_path / "incidents_flow.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        token = _login(client, "owner@test.local", "OwnerPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        alert = client.post(
            "/alerts",
            headers=headers,
            json={
                "alert_type": "manual",
                "severity": "high",
                "chain": "ethereum",
                "address": "0xINCIDENTFLOW0001",
                "score": 88,
                "risk_level": "high",
                "title": "Incident seed alert",
                "body": "Seed alert for incident workflow",
            },
        )
        assert alert.status_code == 200
        alert_id = alert.json()["id"]

        created = client.post(
            "/incidents",
            headers=headers,
            json={
                "title": "Case coordination incident",
                "description": "Track related alert triage",
                "severity": "warning",
                "alert_ids": [alert_id],
            },
        )
        assert created.status_code == 200
        incident = created.json()
        incident_id = incident["id"]
        assert incident["alert_count"] == 1
        assert len(incident["alerts"]) == 1

        listed = client.get("/incidents?limit=10", headers=headers)
        assert listed.status_code == 200
        assert any(item["id"] == incident_id for item in listed.json()["items"])

        fetched = client.get(f"/incidents/{incident_id}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["id"] == incident_id

        updated = client.patch(
            f"/incidents/{incident_id}",
            headers=headers,
            json={"status": "investigating", "severity": "critical"},
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "investigating"
        assert updated.json()["severity"] == "critical"

        second_alert = client.post(
            "/alerts",
            headers=headers,
            json={
                "alert_type": "manual",
                "severity": "warning",
                "chain": "bsc",
                "address": "0xINCIDENTFLOW0002",
                "score": 61,
                "risk_level": "medium",
                "title": "Link target",
                "body": "Attach this alert after incident creation",
            },
        )
        assert second_alert.status_code == 200
        second_alert_id = second_alert.json()["id"]

        linked = client.post(
            f"/incidents/{incident_id}/alerts",
            headers=headers,
            json={"alert_ids": [second_alert_id]},
        )
        assert linked.status_code == 200
        assert linked.json()["linked"] == 1

        after_link = client.get(f"/incidents/{incident_id}", headers=headers)
        assert after_link.status_code == 200
        linked_ids = {item["id"] for item in after_link.json()["alerts"]}
        assert {alert_id, second_alert_id}.issubset(linked_ids)

        unlinked = client.delete(f"/incidents/{incident_id}/alerts/{second_alert_id}", headers=headers)
        assert unlinked.status_code == 200
        assert unlinked.json()["unlinked"] is True

        after_unlink = client.get(f"/incidents/{incident_id}", headers=headers)
        assert after_unlink.status_code == 200
        remaining_ids = {item["id"] for item in after_unlink.json()["alerts"]}
        assert second_alert_id not in remaining_ids
        assert alert_id in remaining_ids


def test_incident_router_blocks_viewer_mutations(tmp_path, monkeypatch):
    db_path = str(tmp_path / "incidents_roles.db")
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
                "email": "viewer-incidents@test.local",
                "password": "ViewerPass123!",
                "role": "viewer",
            },
        )
        assert create_viewer.status_code == 200

        created = client.post(
            "/incidents",
            headers=admin_headers,
            json={
                "title": "Viewer restriction incident",
                "description": "Prepare incident for RBAC checks",
                "severity": "warning",
                "alert_ids": [],
            },
        )
        assert created.status_code == 200
        incident_id = created.json()["id"]

        viewer_token = _login(client, "viewer-incidents@test.local", "ViewerPass123!")
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        viewer_list = client.get("/incidents", headers=viewer_headers)
        assert viewer_list.status_code == 200

        viewer_create = client.post(
            "/incidents",
            headers=viewer_headers,
            json={
                "title": "Forbidden incident",
                "description": "Viewer should not create incidents",
                "severity": "warning",
                "alert_ids": [],
            },
        )
        assert viewer_create.status_code == 403

        viewer_update = client.patch(
            f"/incidents/{incident_id}",
            headers=viewer_headers,
            json={"status": "resolved"},
        )
        assert viewer_update.status_code == 403

        viewer_link = client.post(
            f"/incidents/{incident_id}/alerts",
            headers=viewer_headers,
            json={"alert_ids": [12345]},
        )
        assert viewer_link.status_code == 403


def test_incident_listing_accepts_status_and_severity_filters(tmp_path, monkeypatch):
    db_path = str(tmp_path / "incidents_filters.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        token = _login(client, "owner@test.local", "OwnerPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        critical = client.post(
            "/incidents",
            headers=headers,
            json={
                "title": "Critical incident",
                "description": "Severity filter target",
                "severity": "critical",
                "alert_ids": [],
            },
        )
        assert critical.status_code == 200
        critical_id = critical.json()["id"]

        warning = client.post(
            "/incidents",
            headers=headers,
            json={
                "title": "Warning incident",
                "description": "Status filter target",
                "severity": "warning",
                "alert_ids": [],
            },
        )
        assert warning.status_code == 200
        warning_id = warning.json()["id"]

        updated = client.patch(
            f"/incidents/{warning_id}",
            headers=headers,
            json={"status": "investigating"},
        )
        assert updated.status_code == 200

        by_status = client.get("/incidents?status=investigating&limit=10", headers=headers)
        assert by_status.status_code == 200
        status_items = by_status.json()["items"]
        assert len(status_items) == 1
        assert status_items[0]["id"] == warning_id

        by_severity = client.get("/incidents?severity=critical&limit=10", headers=headers)
        assert by_severity.status_code == 200
        severity_items = by_severity.json()["items"]
        assert len(severity_items) == 1
        assert severity_items[0]["id"] == critical_id
