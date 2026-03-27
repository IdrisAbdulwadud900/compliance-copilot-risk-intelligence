from datetime import datetime, timezone

from app.db import init_db
from app.repositories.webhook_repository import delete_webhook, list_webhooks, save_webhook


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_webhook_repository_flow(tmp_path):
    db_path = str(tmp_path / "webhook_repo.db")
    init_db(db_path)

    created = save_webhook(
        tenant_id="tenant-repo",
        url="https://example.com/repo-webhook",
        events=["alert.fired", "wallet.flagged"],
        created_at=_now(),
        db_path=db_path,
    )
    assert created.id > 0
    assert created.active is True
    assert created.events == ["alert.fired", "wallet.flagged"]

    listed = list_webhooks("tenant-repo", db_path=db_path)
    assert len(listed) == 1
    assert listed[0].id == created.id
    assert listed[0].url == "https://example.com/repo-webhook"

    deleted = delete_webhook(created.id, "tenant-repo", db_path)
    assert deleted is True
    assert list_webhooks("tenant-repo", db_path=db_path) == []
