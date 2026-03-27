from typing import List, Optional

from app.repositories.alert_repository import alert_from_row
from app.schemas import AlertSeverity, IncidentDetail, IncidentStatus, IncidentSummary
from app.storage.runtime import sqlite_connection


INCIDENT_SELECT = """
    SELECT id, tenant_id, title, description, severity, status, alert_count,
           created_at, updated_at, resolved_at, created_by
    FROM incidents
"""


def incident_summary_from_row(row) -> IncidentSummary:
    return IncidentSummary(
        id=row["id"],
        tenant_id=row["tenant_id"],
        title=row["title"],
        description=row["description"],
        severity=row["severity"],
        status=row["status"],
        alert_count=row["alert_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        resolved_at=row["resolved_at"],
        created_by=row["created_by"],
    )


def create_incident(
    tenant_id: str,
    title: str,
    description: str,
    severity: AlertSeverity,
    created_by: str,
    created_at: str,
    alert_ids: Optional[List[int]] = None,
    db_path: Optional[str] = None,
) -> IncidentSummary:
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO incidents
                (tenant_id, title, description, severity, status, alert_count,
                 created_at, updated_at, created_by)
            VALUES (?, ?, ?, ?, 'open', 0, ?, ?, ?)
            """,
            (tenant_id, title, description, severity, created_at, created_at, created_by),
        )
        conn.commit()
        incident_id = cursor.lastrowid if cursor.lastrowid is not None else 0

    for alert_id in (alert_ids or []):
        link_alert_to_incident(alert_id, incident_id, tenant_id, created_at, db_path)

    with sqlite_connection(db_path) as conn:
        row = conn.execute(
            INCIDENT_SELECT + " WHERE id=? AND tenant_id=?",
            (incident_id, tenant_id),
        ).fetchone()
    return incident_summary_from_row(row)


def list_incidents(
    tenant_id: str,
    status: Optional[IncidentStatus] = None,
    severity: Optional[AlertSeverity] = None,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> List[IncidentSummary]:
    conditions: list[str] = ["tenant_id = ?"]
    params: list = [tenant_id]
    if status:
        conditions.append("status = ?")
        params.append(status)
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    where = "WHERE " + " AND ".join(conditions)
    with sqlite_connection(db_path) as conn:
        rows = conn.execute(
            f"{INCIDENT_SELECT} {where} ORDER BY updated_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [incident_summary_from_row(row) for row in rows]


def get_incident_summary(
    incident_id: int, tenant_id: str, db_path: Optional[str] = None
) -> Optional[IncidentSummary]:
    with sqlite_connection(db_path) as conn:
        row = conn.execute(
            INCIDENT_SELECT + " WHERE id=? AND tenant_id=?",
            (incident_id, tenant_id),
        ).fetchone()
    return incident_summary_from_row(row) if row else None


def get_incident_detail(
    incident_id: int, tenant_id: str, db_path: Optional[str] = None
) -> Optional[IncidentDetail]:
    with sqlite_connection(db_path) as conn:
        row = conn.execute(
            INCIDENT_SELECT + " WHERE id=? AND tenant_id=?",
            (incident_id, tenant_id),
        ).fetchone()
        if not row:
            return None
        summary = incident_summary_from_row(row)
        alert_rows = conn.execute(
            """
            SELECT id, tenant_id, created_at, trigger, alert_type, severity, chain, address, score,
                   prev_score, risk_level, title, body, acknowledged, acknowledged_at, resolved_at, incident_id
            FROM alert_events
            WHERE incident_id = ? AND tenant_id = ?
            ORDER BY id DESC
            LIMIT 200
            """,
            (incident_id, tenant_id),
        ).fetchall()
    alerts = [alert_from_row(row) for row in alert_rows]
    return IncidentDetail(**summary.model_dump(), alerts=alerts)


def update_incident(
    incident_id: int,
    tenant_id: str,
    updated_at: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[IncidentStatus] = None,
    severity: Optional[AlertSeverity] = None,
    db_path: Optional[str] = None,
) -> Optional[IncidentSummary]:
    updates: list[str] = ["updated_at = ?"]
    params: list = [updated_at]

    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if severity is not None:
        updates.append("severity = ?")
        params.append(severity)
    if status is not None:
        updates.append("status = ?")
        params.append(status)
        if status == "resolved":
            updates.append("resolved_at = ?")
            params.append(updated_at)
        else:
            updates.append("resolved_at = NULL")

    params.extend([incident_id, tenant_id])
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            f"UPDATE incidents SET {', '.join(updates)} WHERE id=? AND tenant_id=?",
            params,
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            INCIDENT_SELECT + " WHERE id=? AND tenant_id=?",
            (incident_id, tenant_id),
        ).fetchone()
    return incident_summary_from_row(row) if row else None


def link_alert_to_incident(
    alert_id: int,
    incident_id: int,
    tenant_id: str,
    updated_at: str,
    db_path: Optional[str] = None,
) -> bool:
    with sqlite_connection(db_path) as conn:
        alert_row = conn.execute(
            "SELECT id, incident_id FROM alert_events WHERE id=? AND tenant_id=?",
            (alert_id, tenant_id),
        ).fetchone()
        incident_row = conn.execute(
            "SELECT id FROM incidents WHERE id=? AND tenant_id=?",
            (incident_id, tenant_id),
        ).fetchone()
        if not alert_row or not incident_row:
            return False

        old_incident_id = alert_row["incident_id"]
        if old_incident_id and old_incident_id != incident_id:
            conn.execute(
                "UPDATE incidents SET alert_count=MAX(0, alert_count-1), updated_at=? WHERE id=? AND tenant_id=?",
                (updated_at, old_incident_id, tenant_id),
            )
        conn.execute(
            "UPDATE alert_events SET incident_id=? WHERE id=? AND tenant_id=?",
            (incident_id, alert_id, tenant_id),
        )
        if old_incident_id != incident_id:
            conn.execute(
                "UPDATE incidents SET alert_count=alert_count+1, updated_at=? WHERE id=? AND tenant_id=?",
                (updated_at, incident_id, tenant_id),
            )
        conn.commit()
    return True


def unlink_alert_from_incident(
    alert_id: int,
    incident_id: int,
    tenant_id: str,
    updated_at: str,
    db_path: Optional[str] = None,
) -> bool:
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE alert_events SET incident_id=NULL WHERE id=? AND tenant_id=? AND incident_id=?",
            (alert_id, tenant_id, incident_id),
        )
        if cursor.rowcount > 0:
            conn.execute(
                "UPDATE incidents SET alert_count=MAX(0, alert_count-1), updated_at=? WHERE id=? AND tenant_id=?",
                (updated_at, incident_id, tenant_id),
            )
        conn.commit()
        return cursor.rowcount > 0