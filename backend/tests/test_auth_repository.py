from app.db import init_db
from app.repositories.auth_repository import (
    authenticate_user,
    count_users,
    create_invite,
    create_user_if_not_exists,
    list_invites_by_tenant,
    list_recent_audit_logs,
    list_users_by_tenant,
    revoke_invite,
    save_audit_log,
    update_user_password,
)


def test_auth_repository_user_and_audit_flow(tmp_path):
    db_path = str(tmp_path / "auth_repo.db")
    init_db(db_path)

    created = create_user_if_not_exists(
        email="repo-user@test.local",
        password="StrongPass123!",
        tenant_id="tenant-repo",
        role="analyst",
        created_at="2026-03-23T00:00:00Z",
        db_path=db_path,
    )
    assert created.id > 0

    authed = authenticate_user("repo-user@test.local", "StrongPass123!", db_path)
    assert authed == ("repo-user@test.local", "tenant-repo", "analyst")

    update_user_password("repo-user@test.local", "ChangedPass123!", db_path)
    assert authenticate_user("repo-user@test.local", "ChangedPass123!", db_path) == (
        "repo-user@test.local",
        "tenant-repo",
        "analyst",
    )

    users = list_users_by_tenant("tenant-repo", db_path)
    assert len(users) == 1
    assert users[0].email == "repo-user@test.local"
    assert count_users(db_path) == 1

    audit = save_audit_log(
        tenant_id="tenant-repo",
        actor_email="repo-user@test.local",
        action="repo.test",
        target="repository",
        details="repository smoke test",
        created_at="2026-03-23T00:01:00Z",
        db_path=db_path,
    )
    assert audit.id > 0

    audit_items = list_recent_audit_logs("tenant-repo", limit=10, db_path=db_path)
    assert len(audit_items) == 1
    assert audit_items[0].action == "repo.test"


def test_auth_repository_invite_lifecycle(tmp_path):
    db_path = str(tmp_path / "invite_repo.db")
    init_db(db_path)

    token, _ = create_invite(
        email="invitee@test.local",
        tenant_id="tenant-repo",
        role="viewer",
        created_at="2026-03-23T00:00:00Z",
        db_path=db_path,
    )

    invites = list_invites_by_tenant("tenant-repo", limit=10, db_path=db_path)
    assert len(invites) == 1
    assert invites[0].token == token
    assert invites[0].status == "active"

    revoked = revoke_invite(token, "tenant-repo", "2026-03-23T00:02:00Z", db_path)
    assert revoked is True

    invites_after = list_invites_by_tenant("tenant-repo", limit=10, db_path=db_path)
    assert len(invites_after) == 1
    assert invites_after[0].status == "revoked"