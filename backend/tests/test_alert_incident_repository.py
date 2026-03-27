from datetime import datetime, timezone

from app.db import init_db
from app.repositories.alert_repository import (
    acknowledge_alert,
    acknowledge_all_alerts,
    create_alert_manual,
    get_alert_feed,
    list_alert_events,
    list_alerts,
    resolve_alert,
    save_alert_event,
)
from app.repositories.incident_repository import (
    create_incident,
    get_incident_detail,
    link_alert_to_incident,
    list_incidents,
    unlink_alert_from_incident,
    update_incident,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_alert_repository_flow(tmp_path):
    db_path = str(tmp_path / "alert_repo.db")
    init_db(db_path)

    alert_one = save_alert_event(
        tenant_id="tenant-repo",
        trigger="score_threshold",
        chain="ethereum",
        address="0xALERTREPO1",
        score=87,
        risk_level="critical",
        title="Repo alert 1",
        body="Initial alert",
        created_at=_now(),
        alert_type="score_threshold",
        severity="critical",
        db_path=db_path,
    )
    alert_two = create_alert_manual(
        tenant_id="tenant-repo",
        alert_type="manual",
        severity="warning",
        chain="bsc",
        address="0xALERTREPO2",
        score=52,
        risk_level="medium",
        title="Repo alert 2",
        body="Manual alert",
        created_at=_now(),
        db_path=db_path,
    )

    listed = list_alerts("tenant-repo", limit=10, db_path=db_path)
    assert len(listed) == 2
    assert {item.id for item in listed} == {alert_one.id, alert_two.id}

    events = list_alert_events("tenant-repo", limit=10, db_path=db_path)
    assert len(events) == 2

    assert acknowledge_alert(alert_one.id, "tenant-repo", _now(), db_path)
    count = acknowledge_all_alerts("tenant-repo", _now(), db_path)
    assert count == 1

    assert resolve_alert(alert_two.id, "tenant-repo", _now(), db_path)
    feed = get_alert_feed("tenant-repo", since_id=0, limit=10, db_path=db_path)
    assert len(feed) == 2
    assert feed[0].id < feed[1].id


def test_incident_repository_flow(tmp_path):
    db_path = str(tmp_path / "incident_repo.db")
    init_db(db_path)

    alert = save_alert_event(
        tenant_id="tenant-repo",
        trigger="watchlist_activity",
        chain="ethereum",
        address="0xINCIDENTREPO1",
        score=72,
        risk_level="high",
        title="Incident source",
        body="Repo incident seed",
        created_at=_now(),
        alert_type="watchlist_hit",
        severity="high",
        db_path=db_path,
    )

    incident = create_incident(
        tenant_id="tenant-repo",
        title="Repo incident",
        description="Repository-backed incident",
        severity="high",
        created_by="repo@test.local",
        created_at=_now(),
        alert_ids=[alert.id],
        db_path=db_path,
    )
    assert incident.alert_count == 1

    listed = list_incidents("tenant-repo", db_path=db_path)
    assert len(listed) == 1
    assert listed[0].id == incident.id

    detail = get_incident_detail(incident.id, "tenant-repo", db_path=db_path)
    assert detail is not None
    assert len(detail.alerts) == 1

    updated = update_incident(incident.id, "tenant-repo", _now(), status="resolved", db_path=db_path)
    assert updated is not None
    assert updated.status == "resolved"

    second_alert = save_alert_event(
        tenant_id="tenant-repo",
        trigger="score_threshold",
        chain="bsc",
        address="0xINCIDENTREPO2",
        score=65,
        risk_level="high",
        title="Second source",
        body="Second repo incident seed",
        created_at=_now(),
        db_path=db_path,
    )
    assert link_alert_to_incident(second_alert.id, incident.id, "tenant-repo", _now(), db_path)
    assert unlink_alert_from_incident(second_alert.id, incident.id, "tenant-repo", _now(), db_path)