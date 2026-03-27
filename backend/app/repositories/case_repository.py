from typing import List, Optional

from app.schemas import (
    AuditEntry,
    CaseAttachment,
    CaseDetail,
    CaseEntity,
    CaseEntityType,
    CaseEventType,
    CaseNote,
    CasePriority,
    CaseStatus,
    CaseSummary,
    CaseTimelineEvent,
    RiskLevel,
)
from app.storage.runtime import sqlite_connection


def parse_tags(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def serialize_tags(tags: List[str]) -> str:
    return ",".join(tag.strip() for tag in tags if tag.strip())


def case_summary_from_row(row) -> CaseSummary:
    return CaseSummary(
        id=row["id"],
        tenant_id=row["tenant_id"],
        title=row["title"],
        status=row["status"],
        priority=row["priority"],
        summary=row["summary"],
        owner_email=row["owner_email"],
        source_type=row["source_type"],
        source_ref=row["source_ref"],
        primary_chain=row["primary_chain"],
        primary_address=row["primary_address"],
        risk_score=row["risk_score"],
        risk_level=row["risk_level"],
        tags=parse_tags(row["tags"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        closed_at=row["closed_at"],
    )


def case_event_from_row(row) -> CaseTimelineEvent:
    return CaseTimelineEvent(
        id=row["id"],
        case_id=row["case_id"],
        event_type=row["event_type"],
        actor_email=row["actor_email"],
        title=row["title"],
        body=row["body"],
        created_at=row["created_at"],
    )


def case_note_from_row(row) -> CaseNote:
    return CaseNote(
        id=row["id"],
        case_id=row["case_id"],
        note_type=row["note_type"],
        body=row["body"],
        tags=parse_tags(row["tags"]),
        author_email=row["author_email"],
        created_at=row["created_at"],
    )


def case_entity_from_row(row) -> CaseEntity:
    return CaseEntity(
        id=row["id"],
        case_id=row["case_id"],
        entity_type=row["entity_type"],
        label=row["label"],
        chain=row["chain"],
        reference=row["reference"],
        risk_score=row["risk_score"],
        risk_level=row["risk_level"],
        created_at=row["created_at"],
    )


def case_attachment_from_row(row) -> CaseAttachment:
    return CaseAttachment(
        id=row["id"],
        case_id=row["case_id"],
        file_name=row["file_name"],
        file_url=row["file_url"],
        content_type=row["content_type"],
        uploaded_by=row["uploaded_by"],
        created_at=row["created_at"],
    )


def touch_case(case_id: int, updated_at: str, db_path: Optional[str] = None) -> None:
    with sqlite_connection(db_path) as conn:
        conn.execute(
            "UPDATE cases SET updated_at = ? WHERE id = ?",
            (updated_at, case_id),
        )
        conn.commit()


def create_case(
    tenant_id: str,
    title: str,
    summary: str,
    priority: CasePriority,
    owner_email: str,
    source_type: str,
    source_ref: str,
    primary_chain: str,
    primary_address: str,
    risk_score: int,
    risk_level: RiskLevel,
    tags: List[str],
    created_at: str,
    db_path: Optional[str] = None,
) -> CaseSummary:
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO cases (
                tenant_id, title, status, priority, summary, owner_email,
                source_type, source_ref, primary_chain, primary_address,
                risk_score, risk_level, tags, created_at, updated_at, closed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                tenant_id,
                title,
                "open",
                priority,
                summary,
                owner_email,
                source_type,
                source_ref,
                primary_chain,
                primary_address.strip().lower(),
                risk_score,
                risk_level,
                serialize_tags(tags),
                created_at,
                created_at,
            ),
        )
        case_id = cursor.lastrowid if cursor.lastrowid is not None else 0
        conn.execute(
            """
            INSERT INTO case_events (case_id, tenant_id, event_type, actor_email, title, body, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                tenant_id,
                "case_created",
                owner_email or "system",
                "Case opened",
                f"Investigation '{title}' was created.",
                created_at,
            ),
        )
        row = conn.execute(
            "SELECT * FROM cases WHERE id = ? AND tenant_id = ?",
            (case_id, tenant_id),
        ).fetchone()
        conn.commit()

    if row is None:
        raise ValueError("Failed to create case")
    return case_summary_from_row(row)


def list_cases(
    tenant_id: str,
    limit: int = 50,
    status: Optional[CaseStatus] = None,
    db_path: Optional[str] = None,
) -> List[CaseSummary]:
    query = "SELECT * FROM cases WHERE tenant_id = ?"
    params: List[object] = [tenant_id]
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY updated_at DESC, id DESC LIMIT ?"
    params.append(limit)

    with sqlite_connection(db_path) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()

    return [case_summary_from_row(row) for row in rows]


def get_case_summary(
    case_id: int,
    tenant_id: str,
    db_path: Optional[str] = None,
) -> Optional[CaseSummary]:
    with sqlite_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM cases WHERE id = ? AND tenant_id = ?",
            (case_id, tenant_id),
        ).fetchone()

    if row is None:
        return None
    return case_summary_from_row(row)


def list_case_timeline(
    case_id: int,
    tenant_id: str,
    db_path: Optional[str] = None,
) -> List[CaseTimelineEvent]:
    with sqlite_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, case_id, event_type, actor_email, title, body, created_at
            FROM case_events
            WHERE case_id = ? AND tenant_id = ?
            ORDER BY id DESC
            """,
            (case_id, tenant_id),
        ).fetchall()

    return [case_event_from_row(row) for row in rows]


def list_case_notes(
    case_id: int,
    tenant_id: str,
    db_path: Optional[str] = None,
) -> List[CaseNote]:
    with sqlite_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, case_id, note_type, body, tags, author_email, created_at
            FROM case_notes
            WHERE case_id = ? AND tenant_id = ?
            ORDER BY id DESC
            """,
            (case_id, tenant_id),
        ).fetchall()

    return [case_note_from_row(row) for row in rows]


def list_case_entities(
    case_id: int,
    tenant_id: str,
    db_path: Optional[str] = None,
) -> List[CaseEntity]:
    with sqlite_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, case_id, entity_type, label, chain, reference, risk_score, risk_level, created_at
            FROM case_entities
            WHERE case_id = ? AND tenant_id = ?
            ORDER BY id DESC
            """,
            (case_id, tenant_id),
        ).fetchall()

    return [case_entity_from_row(row) for row in rows]


def list_case_attachments(
    case_id: int,
    tenant_id: str,
    db_path: Optional[str] = None,
) -> List[CaseAttachment]:
    with sqlite_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, case_id, file_name, file_url, content_type, uploaded_by, created_at
            FROM case_attachments
            WHERE case_id = ? AND tenant_id = ?
            ORDER BY id DESC
            """,
            (case_id, tenant_id),
        ).fetchall()

    return [case_attachment_from_row(row) for row in rows]


def list_case_activity(
    case_id: int,
    tenant_id: str,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> List[AuditEntry]:
    target = f"case:{case_id}"
    with sqlite_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, actor_email, action, target, details
            FROM audit_logs
            WHERE tenant_id = ? AND target = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (tenant_id, target, limit),
        ).fetchall()

    return [
        AuditEntry(
            id=row["id"],
            created_at=row["created_at"],
            actor_email=row["actor_email"],
            action=row["action"],
            target=row["target"],
            details=row["details"],
        )
        for row in rows
    ]


def get_case_detail(
    case_id: int,
    tenant_id: str,
    db_path: Optional[str] = None,
) -> Optional[CaseDetail]:
    summary = get_case_summary(case_id, tenant_id, db_path)
    if summary is None:
        return None

    return CaseDetail(
        **summary.model_dump(),
        timeline=list_case_timeline(case_id, tenant_id, db_path),
        notes=list_case_notes(case_id, tenant_id, db_path),
        linked_entities=list_case_entities(case_id, tenant_id, db_path),
        attachments=list_case_attachments(case_id, tenant_id, db_path),
        activity=list_case_activity(case_id, tenant_id, db_path=db_path),
    )


def append_case_event(
    case_id: int,
    tenant_id: str,
    event_type: CaseEventType,
    actor_email: str,
    title: str,
    body: str,
    created_at: str,
    db_path: Optional[str] = None,
) -> CaseTimelineEvent:
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO case_events (case_id, tenant_id, event_type, actor_email, title, body, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (case_id, tenant_id, event_type, actor_email, title, body, created_at),
        )
        conn.execute(
            "UPDATE cases SET updated_at = ? WHERE id = ?",
            (created_at, case_id),
        )
        row_id = cursor.lastrowid if cursor.lastrowid is not None else 0
        row = conn.execute(
            "SELECT id, case_id, event_type, actor_email, title, body, created_at FROM case_events WHERE id = ?",
            (row_id,),
        ).fetchone()
        conn.commit()

    if row is None:
        raise ValueError("Failed to append case event")
    return case_event_from_row(row)


def update_case(
    case_id: int,
    tenant_id: str,
    updated_at: str,
    status: Optional[CaseStatus] = None,
    priority: Optional[CasePriority] = None,
    summary: Optional[str] = None,
    owner_email: Optional[str] = None,
    tags: Optional[List[str]] = None,
    db_path: Optional[str] = None,
) -> Optional[CaseSummary]:
    updates: List[str] = []
    params: List[object] = []

    if status is not None:
        updates.append("status = ?")
        params.append(status)
        updates.append("closed_at = ?")
        params.append(updated_at if status == "closed" else None)
    if priority is not None:
        updates.append("priority = ?")
        params.append(priority)
    if summary is not None:
        updates.append("summary = ?")
        params.append(summary)
    if owner_email is not None:
        updates.append("owner_email = ?")
        params.append(owner_email)
    if tags is not None:
        updates.append("tags = ?")
        params.append(serialize_tags(tags))

    if not updates:
        return get_case_summary(case_id, tenant_id, db_path)

    updates.append("updated_at = ?")
    params.append(updated_at)
    params.extend([case_id, tenant_id])

    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            f"UPDATE cases SET {', '.join(updates)} WHERE id = ? AND tenant_id = ?",
            tuple(params),
        )
        if cursor.rowcount == 0:
            conn.commit()
            return None

        row = conn.execute(
            "SELECT * FROM cases WHERE id = ? AND tenant_id = ?",
            (case_id, tenant_id),
        ).fetchone()
        conn.commit()

    if row is None:
        return None
    return case_summary_from_row(row)


def add_case_note(
    case_id: int,
    tenant_id: str,
    note_type: str,
    body: str,
    tags: List[str],
    author_email: str,
    created_at: str,
    db_path: Optional[str] = None,
) -> Optional[CaseNote]:
    if get_case_summary(case_id, tenant_id, db_path) is None:
        return None

    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO case_notes (case_id, tenant_id, note_type, body, tags, author_email, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (case_id, tenant_id, note_type, body, serialize_tags(tags), author_email, created_at),
        )
        conn.execute(
            "UPDATE cases SET updated_at = ? WHERE id = ?",
            (created_at, case_id),
        )
        row_id = cursor.lastrowid if cursor.lastrowid is not None else 0
        row = conn.execute(
            "SELECT id, case_id, note_type, body, tags, author_email, created_at FROM case_notes WHERE id = ?",
            (row_id,),
        ).fetchone()
        conn.commit()

    if row is None:
        return None
    return case_note_from_row(row)


def add_case_entity(
    case_id: int,
    tenant_id: str,
    entity_type: CaseEntityType,
    label: str,
    chain: str,
    reference: str,
    risk_score: Optional[int],
    risk_level: Optional[RiskLevel],
    created_at: str,
    db_path: Optional[str] = None,
) -> Optional[CaseEntity]:
    if get_case_summary(case_id, tenant_id, db_path) is None:
        return None

    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO case_entities (
                case_id, tenant_id, entity_type, label, chain, reference, risk_score, risk_level, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (case_id, tenant_id, entity_type, label, chain, reference, risk_score, risk_level, created_at),
        )
        conn.execute(
            "UPDATE cases SET updated_at = ? WHERE id = ?",
            (created_at, case_id),
        )
        row_id = cursor.lastrowid if cursor.lastrowid is not None else 0
        row = conn.execute(
            "SELECT id, case_id, entity_type, label, chain, reference, risk_score, risk_level, created_at FROM case_entities WHERE id = ?",
            (row_id,),
        ).fetchone()
        conn.commit()

    if row is None:
        return None
    return case_entity_from_row(row)


def add_case_attachment(
    case_id: int,
    tenant_id: str,
    file_name: str,
    file_url: str,
    content_type: str,
    uploaded_by: str,
    created_at: str,
    db_path: Optional[str] = None,
) -> Optional[CaseAttachment]:
    if get_case_summary(case_id, tenant_id, db_path) is None:
        return None

    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO case_attachments (
                case_id, tenant_id, file_name, file_url, content_type, uploaded_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (case_id, tenant_id, file_name, file_url, content_type, uploaded_by, created_at),
        )
        conn.execute(
            "UPDATE cases SET updated_at = ? WHERE id = ?",
            (created_at, case_id),
        )
        row_id = cursor.lastrowid if cursor.lastrowid is not None else 0
        row = conn.execute(
            "SELECT id, case_id, file_name, file_url, content_type, uploaded_by, created_at FROM case_attachments WHERE id = ?",
            (row_id,),
        ).fetchone()
        conn.commit()

    if row is None:
        return None
    return case_attachment_from_row(row)
