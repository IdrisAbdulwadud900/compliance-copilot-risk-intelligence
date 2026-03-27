from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_case_management_flow(tmp_path, monkeypatch):
    db_path = str(tmp_path / "cases_flow.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        token = _login(client, "owner@test.local", "OwnerPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post(
            "/cases",
            headers=headers,
            json={
                "title": "Bridge exposure escalation",
                "summary": "Investigate wallet linked to elevated mixer and sanctions exposure.",
                "priority": "high",
                "primary_chain": "ethereum",
                "primary_address": "0xABCDEF1122334455",
                "risk_score": 88,
                "risk_level": "critical",
                "tags": ["bridge", "urgent"],
            },
        )
        assert created.status_code == 200
        created_case = created.json()
        case_id = created_case["id"]
        assert created_case["status"] == "open"
        assert created_case["timeline"][0]["event_type"] == "case_created"

        listing = client.get("/cases?limit=10", headers=headers)
        assert listing.status_code == 200
        listing_payload = listing.json()
        assert len(listing_payload["items"]) == 1
        assert listing_payload["items"][0]["id"] == case_id

        note = client.post(
            f"/cases/{case_id}/notes",
            headers=headers,
            json={
                "note_type": "evidence",
                "body": "Cross-chain movement suggests layered obfuscation.",
                "tags": ["triage"],
            },
        )
        assert note.status_code == 200
        assert note.json()["note_type"] == "evidence"

        entity = client.post(
            f"/cases/{case_id}/entities",
            headers=headers,
            json={
                "entity_type": "wallet",
                "label": "Primary suspect wallet",
                "chain": "ethereum",
                "reference": "0xABCDEF1122334455",
                "risk_score": 88,
                "risk_level": "critical",
            },
        )
        assert entity.status_code == 200
        assert entity.json()["entity_type"] == "wallet"

        attachment = client.post(
            f"/cases/{case_id}/attachments",
            headers=headers,
            json={
                "file_name": "TRM export",
                "file_url": "https://example.com/evidence/trm-export",
                "content_type": "link",
            },
        )
        assert attachment.status_code == 200
        assert attachment.json()["file_name"] == "TRM export"

        updated = client.patch(
            f"/cases/{case_id}",
            headers=headers,
            json={"status": "escalated", "tags": ["bridge", "urgent", "escalated"]},
        )
        assert updated.status_code == 200
        updated_case = updated.json()
        assert updated_case["status"] == "escalated"
        assert any(event["event_type"] == "status_changed" for event in updated_case["timeline"])
        assert len(updated_case["notes"]) == 1
        assert len(updated_case["linked_entities"]) == 1
        assert len(updated_case["attachments"]) == 1

        detail = client.get(f"/cases/{case_id}", headers=headers)
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["activity"]
        assert detail_payload["activity"][0]["target"] == f"case:{case_id}"


def test_case_management_blocks_viewer_mutations(tmp_path, monkeypatch):
    db_path = str(tmp_path / "cases_roles.db")
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
                "email": "viewer-cases@test.local",
                "password": "ViewerPass123!",
                "role": "viewer",
            },
        )
        assert create_viewer.status_code == 200

        created = client.post(
            "/cases",
            headers=admin_headers,
            json={
                "title": "Viewer restriction case",
                "summary": "Used for RBAC validation",
                "priority": "medium",
                "primary_chain": "ethereum",
                "primary_address": "0xCASESVIEW0001",
                "risk_score": 45,
                "risk_level": "medium",
                "tags": ["rbac"],
            },
        )
        assert created.status_code == 200
        case_id = created.json()["id"]

        viewer_token = _login(client, "viewer-cases@test.local", "ViewerPass123!")
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        viewer_list = client.get("/cases?limit=10", headers=viewer_headers)
        assert viewer_list.status_code == 200

        viewer_create = client.post(
            "/cases",
            headers=viewer_headers,
            json={
                "title": "Forbidden case",
                "summary": "Viewer should not create cases",
                "priority": "low",
                "primary_chain": "ethereum",
                "primary_address": "0xCASESVIEW0002",
                "risk_score": 5,
                "risk_level": "low",
                "tags": [],
            },
        )
        assert viewer_create.status_code == 403

        viewer_update = client.patch(
            f"/cases/{case_id}",
            headers=viewer_headers,
            json={"status": "closed"},
        )
        assert viewer_update.status_code == 403

        viewer_note = client.post(
            f"/cases/{case_id}/notes",
            headers=viewer_headers,
            json={"note_type": "observation", "body": "Blocked", "tags": []},
        )
        assert viewer_note.status_code == 403


def test_case_listing_accepts_status_query_alias(tmp_path, monkeypatch):
    db_path = str(tmp_path / "cases_status_filter.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        token = _login(client, "owner@test.local", "OwnerPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post(
            "/cases",
            headers=headers,
            json={
                "title": "Status alias case",
                "summary": "Ensure frontend status query param filters correctly.",
                "priority": "high",
                "primary_chain": "ethereum",
                "primary_address": "0xCASEFILTER0001",
                "risk_score": 72,
                "risk_level": "high",
                "tags": ["filter"],
            },
        )
        assert created.status_code == 200
        case_id = created.json()["id"]

        updated = client.patch(
            f"/cases/{case_id}",
            headers=headers,
            json={"status": "escalated"},
        )
        assert updated.status_code == 200

        filtered = client.get("/cases?status=escalated&limit=10", headers=headers)
        assert filtered.status_code == 200
        items = filtered.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == case_id
