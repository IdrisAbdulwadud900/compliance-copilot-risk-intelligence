from datetime import datetime, timezone

from app.db import init_db
from app.repositories.watchlist_repository import (
    add_to_watchlist,
    is_on_watchlist,
    list_watchlist,
    remove_from_watchlist,
    touch_watchlist_entry,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_watchlist_repository_flow(tmp_path):
    db_path = str(tmp_path / "watchlist_repo.db")
    init_db(db_path)

    created = add_to_watchlist(
        tenant_id="tenant-repo",
        chain="ethereum",
        address="0xWATCHREPO1",
        label="Repository watch",
        created_at=_now(),
        created_by="repo@test.local",
        alert_on_activity=True,
        db_path=db_path,
    )
    assert created is not None
    assert created.address == "0xwatchrepo1"
    assert created.alert_on_activity is True

    duplicate = add_to_watchlist(
        tenant_id="tenant-repo",
        chain="ethereum",
        address="0xWATCHREPO1",
        label="Repository watch",
        created_at=_now(),
        created_by="repo@test.local",
        alert_on_activity=True,
        db_path=db_path,
    )
    assert duplicate is None

    listed = list_watchlist("tenant-repo", db_path=db_path)
    assert len(listed) == 1
    assert listed[0].id == created.id

    found = is_on_watchlist("tenant-repo", "ethereum", "0xWATCHREPO1", db_path=db_path)
    assert found is not None
    assert found.id == created.id

    seen_at = _now()
    touched = touch_watchlist_entry(
        "tenant-repo",
        "ethereum",
        "0xWATCHREPO1",
        77,
        seen_at,
        db_path,
    )
    assert touched is True

    refreshed = is_on_watchlist("tenant-repo", "ethereum", "0xwatchrepo1", db_path=db_path)
    assert refreshed is not None
    assert refreshed.last_score == 77
    assert refreshed.last_seen_at == seen_at

    removed = remove_from_watchlist("tenant-repo", created.id, db_path)
    assert removed is True
    assert is_on_watchlist("tenant-repo", "ethereum", "0xWATCHREPO1", db_path=db_path) is None
