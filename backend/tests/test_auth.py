from app.auth import get_current_principal, get_current_tenant, login_and_issue_token
from app.db import init_db


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
