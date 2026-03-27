from datetime import datetime, timezone

from app.db import init_db, save_audit_log
from app.repositories.case_repository import (
    add_case_attachment,
    add_case_entity,
    add_case_note,
    append_case_event,
    create_case,
    get_case_detail,
    list_case_activity,
    list_cases,
    update_case,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_case_repository_flow(tmp_path):
    db_path = str(tmp_path / "case_repo.db")
    init_db(db_path)

    created_at = _now()
    case = create_case(
        tenant_id="tenant-repo",
        title="Repository case",
        summary="Repository extraction regression",
        priority="high",
        owner_email="repo@test.local",
        source_type="manual",
        source_ref="repo-seed",
        primary_chain="ethereum",
        primary_address="0xCASEREPO1",
        risk_score=84,
        risk_level="critical",
        tags=["repo", "triage"],
        created_at=created_at,
        db_path=db_path,
    )
    assert case.status == "open"
    assert case.primary_address == "0xcaserepo1"

    listed = list_cases("tenant-repo", limit=10, db_path=db_path)
    assert len(listed) == 1
    assert listed[0].id == case.id

    note = add_case_note(
        case.id,
        "tenant-repo",
        "evidence",
        "Escalation note",
        ["urgent"],
        "repo@test.local",
        _now(),
        db_path,
    )
    assert note is not None
    assert note.tags == ["urgent"]

    entity = add_case_entity(
        case.id,
        "tenant-repo",
        "wallet",
        "Suspect wallet",
        "ethereum",
        "0xCASEREPO1",
        84,
        "critical",
        _now(),
        db_path,
    )
    assert entity is not None
    assert entity.entity_type == "wallet"

    attachment = add_case_attachment(
        case.id,
        "tenant-repo",
        "Evidence link",
        "https://example.com/repo-evidence",
        "link",
        "repo@test.local",
        _now(),
        db_path,
    )
    assert attachment is not None
    assert attachment.file_name == "Evidence link"

    event = append_case_event(
        case.id,
        "tenant-repo",
        "status_changed",
        "repo@test.local",
        "Status updated",
        "Case escalated",
        _now(),
        db_path,
    )
    assert event.event_type == "status_changed"

    updated = update_case(
        case.id,
        "tenant-repo",
        _now(),
        status="escalated",
        tags=["repo", "urgent", "escalated"],
        db_path=db_path,
    )
    assert updated is not None
    assert updated.status == "escalated"
    assert "escalated" in updated.tags

    save_audit_log(
        tenant_id="tenant-repo",
        actor_email="repo@test.local",
        action="case.update",
        target=f"case:{case.id}",
        details="Repository audit entry",
        created_at=_now(),
        db_path=db_path,
    )

    activity = list_case_activity(case.id, "tenant-repo", db_path=db_path)
    assert len(activity) == 1
    assert activity[0].target == f"case:{case.id}"

    detail = get_case_detail(case.id, "tenant-repo", db_path=db_path)
    assert detail is not None
    assert len(detail.timeline) == 2
    assert len(detail.notes) == 1
    assert len(detail.linked_entities) == 1
    assert len(detail.attachments) == 1
    assert len(detail.activity) == 1
