from app.db import init_db, list_recent_audit_logs, save_audit_log


def test_save_and_list_audit_logs(tmp_path):
    db_path = str(tmp_path / "audit.db")
    init_db(db_path)

    entry = save_audit_log(
        tenant_id="tenant-a",
        actor_email="admin@test.local",
        action="analysis.explain",
        target="0xABCDEF",
        details="Score=66 level=high",
        created_at="2026-03-21T00:00:00Z",
        db_path=db_path,
    )
    assert entry.id > 0

    items = list_recent_audit_logs(tenant_id="tenant-a", limit=10, db_path=db_path)
    assert len(items) == 1
    assert items[0].action == "analysis.explain"

    other = list_recent_audit_logs(tenant_id="tenant-b", limit=10, db_path=db_path)
    assert other == []
