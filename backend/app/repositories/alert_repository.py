from datetime import datetime, timezone
from typing import List, Optional

from app.schemas import Alert, AlertSeverity, AlertTrigger, AlertType, Blockchain, RiskLevel
from app.storage.runtime import sqlite_connection


def alert_from_row(row) -> Alert:
    return Alert(
        id=row["id"],
        tenant_id=row["tenant_id"],
        created_at=row["created_at"],
        trigger=row["trigger"],
        alert_type=row["alert_type"],
        severity=row["severity"],
        chain=row["chain"],
        address=row["address"],
        score=row["score"],
        prev_score=row["prev_score"],
        risk_level=row["risk_level"],
        title=row["title"],
        body=row["body"],
        acknowledged=bool(row["acknowledged"]),
        acknowledged_at=row["acknowledged_at"],
        resolved_at=row["resolved_at"],
        incident_id=row["incident_id"],
    )


def save_alert_event(
    tenant_id: str,
    trigger: AlertTrigger,
    chain: Blockchain,
    address: str,
    score: int,
    risk_level: RiskLevel,
    title: str,
    body: str,
    created_at: str,
    alert_type: AlertType = "score_threshold",
    severity: AlertSeverity = "warning",
    prev_score: Optional[int] = None,
    db_path: Optional[str] = None,
) -> Alert:
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO alert_events
                (tenant_id, created_at, trigger, chain, address, score, risk_level,
                 title, body, alert_type, severity, prev_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tenant_id, created_at, trigger, chain, address, score, risk_level,
             title, body, alert_type, severity, prev_score),
        )
        conn.commit()
        row_id = cursor.lastrowid if cursor.lastrowid is not None else 0
    return Alert(
        id=row_id,
        tenant_id=tenant_id,
        created_at=created_at,
        trigger=trigger,
        alert_type=alert_type,
        severity=severity,
        chain=chain,
        address=address,
        score=score,
        prev_score=prev_score,
        risk_level=risk_level,
        title=title,
        body=body,
        acknowledged=False,
    )


def list_alert_events(
    tenant_id: str, limit: int = 50, unacked_only: bool = False, db_path: Optional[str] = None
) -> List[Alert]:
    where = "WHERE tenant_id = ?"
    params: list = [tenant_id]
    if unacked_only:
        where += " AND acknowledged = 0"
    with sqlite_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT id, tenant_id, created_at, trigger, alert_type, severity, chain, address, score,
                   prev_score, risk_level, title, body, acknowledged, acknowledged_at, resolved_at, incident_id
            FROM alert_events
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [alert_from_row(row) for row in rows]


def acknowledge_alert(
    alert_id: int, tenant_id: str, acked_at: Optional[str] = None, db_path: Optional[str] = None
) -> bool:
    ts = acked_at or datetime.now(timezone.utc).isoformat()
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE alert_events SET acknowledged=1, acknowledged_at=? WHERE id=? AND tenant_id=?",
            (ts, alert_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def acknowledge_all_alerts(
    tenant_id: str, acked_at: str, db_path: Optional[str] = None
) -> int:
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE alert_events SET acknowledged=1, acknowledged_at=? WHERE tenant_id=? AND acknowledged=0",
            (acked_at, tenant_id),
        )
        conn.commit()
        return cursor.rowcount


def resolve_alert(
    alert_id: int, tenant_id: str, resolved_at: str, db_path: Optional[str] = None
) -> bool:
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE alert_events SET resolved_at=?, acknowledged=1, acknowledged_at=? WHERE id=? AND tenant_id=?",
            (resolved_at, resolved_at, alert_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def create_alert_manual(
    tenant_id: str,
    alert_type: AlertType,
    severity: AlertSeverity,
    chain: Blockchain,
    address: str,
    score: int,
    risk_level: RiskLevel,
    title: str,
    body: str,
    created_at: str,
    db_path: Optional[str] = None,
) -> Alert:
    return save_alert_event(
        tenant_id=tenant_id,
        trigger="manual",
        chain=chain,
        address=address,
        score=score,
        risk_level=risk_level,
        title=title,
        body=body,
        created_at=created_at,
        alert_type=alert_type,
        severity=severity,
        db_path=db_path,
    )


def list_alerts(
    tenant_id: str,
    limit: int = 50,
    severity: Optional[AlertSeverity] = None,
    alert_type: Optional[AlertType] = None,
    unacked_only: bool = False,
    incident_id: Optional[int] = None,
    since_id: int = 0,
    db_path: Optional[str] = None,
) -> List[Alert]:
    conditions: list[str] = ["tenant_id = ?"]
    params: list = [tenant_id]

    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    if alert_type:
        conditions.append("alert_type = ?")
        params.append(alert_type)
    if unacked_only:
        conditions.append("acknowledged = 0")
    if incident_id is not None:
        conditions.append("incident_id = ?")
        params.append(incident_id)
    if since_id > 0:
        conditions.append("id > ?")
        params.append(since_id)

    where = "WHERE " + " AND ".join(conditions)
    order = "ORDER BY id ASC" if since_id > 0 else "ORDER BY id DESC"

    with sqlite_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT id, tenant_id, created_at, trigger, alert_type, severity, chain, address, score,
                   prev_score, risk_level, title, body, acknowledged, acknowledged_at, resolved_at, incident_id
            FROM alert_events
            {where}
            {order}
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [alert_from_row(row) for row in rows]


def get_alert_feed(
    tenant_id: str,
    since_id: int = 0,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> List[Alert]:
    with sqlite_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, tenant_id, created_at, trigger, alert_type, severity, chain, address, score,
                   prev_score, risk_level, title, body, acknowledged, acknowledged_at, resolved_at, incident_id
            FROM alert_events
            WHERE tenant_id = ? AND id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (tenant_id, since_id, limit),
        ).fetchall()
    return [alert_from_row(row) for row in rows]