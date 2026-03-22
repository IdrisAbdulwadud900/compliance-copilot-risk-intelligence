from app.db import create_user_if_not_exists, init_db, list_users_by_tenant


def test_create_and_list_users_by_tenant(tmp_path):
    db_path = str(tmp_path / "users.db")
    init_db(db_path)

    created = create_user_if_not_exists(
        email="analyst@test.local",
        password="StrongPass123!",
        tenant_id="tenant-a",
        role="analyst",
        created_at="2026-03-21T00:00:00Z",
        db_path=db_path,
    )
    assert created.id > 0
    assert created.role == "analyst"

    same = create_user_if_not_exists(
        email="analyst@test.local",
        password="OtherPass123!",
        tenant_id="tenant-a",
        role="viewer",
        created_at="2026-03-21T00:00:01Z",
        db_path=db_path,
    )
    assert same.id == created.id

    users = list_users_by_tenant("tenant-a", db_path=db_path)
    assert any(u.email == "analyst@test.local" for u in users)

    users_other = list_users_by_tenant("tenant-b", db_path=db_path)
    assert users_other == []
