from typing import List, Optional

from app.schemas import WebhookConfig, WebhookEvent
from app.storage.runtime import sqlite_connection


def webhook_from_row(row) -> WebhookConfig:
    return WebhookConfig(
        id=row["id"],
        tenant_id=row["tenant_id"],
        url=row["url"],
        events=row["events"].split(",") if row["events"] else [],
        created_at=row["created_at"],
        active=bool(row["active"]),
    )


def save_webhook(
    tenant_id: str,
    url: str,
    events: List[WebhookEvent],
    created_at: str,
    db_path: Optional[str] = None,
) -> WebhookConfig:
    events_str = ",".join(events)
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO webhooks (tenant_id, url, events, created_at, active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (tenant_id, url, events_str, created_at),
        )
        conn.commit()
        row_id = cursor.lastrowid if cursor.lastrowid is not None else 0
    return WebhookConfig(
        id=row_id,
        tenant_id=tenant_id,
        url=url,
        events=events,
        created_at=created_at,
        active=True,
    )


def list_webhooks(tenant_id: str, db_path: Optional[str] = None) -> List[WebhookConfig]:
    with sqlite_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, tenant_id, url, events, created_at, active FROM webhooks WHERE tenant_id=? AND active=1",
            (tenant_id,),
        ).fetchall()
    return [webhook_from_row(row) for row in rows]


def delete_webhook(webhook_id: int, tenant_id: str, db_path: Optional[str] = None) -> bool:
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE webhooks SET active=0 WHERE id=? AND tenant_id=?",
            (webhook_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0
