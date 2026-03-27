from typing import List, Optional

from app.schemas import Blockchain, WatchlistEntry
from app.storage.runtime import sqlite_connection


def watchlist_entry_from_row(row) -> WatchlistEntry:
    return WatchlistEntry(
        id=row["id"],
        tenant_id=row["tenant_id"],
        chain=row["chain"],
        address=row["address"],
        label=row["label"],
        created_at=row["created_at"],
        created_by=row["created_by"],
        last_seen_at=row["last_seen_at"],
        last_score=row["last_score"],
        alert_on_activity=bool(row["alert_on_activity"]),
    )


def add_to_watchlist(
    tenant_id: str,
    chain: Blockchain,
    address: str,
    label: str,
    created_at: str,
    created_by: str,
    alert_on_activity: bool = True,
    db_path: Optional[str] = None,
) -> Optional[WatchlistEntry]:
    normalized_address = address.strip().lower()
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO watchlist
                (tenant_id, chain, address, label, created_at, created_by, alert_on_activity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tenant_id, chain, normalized_address, label, created_at, created_by, int(alert_on_activity)),
        )
        conn.commit()
        row_id = cursor.lastrowid if cursor.lastrowid and cursor.rowcount > 0 else None

    if row_id is None:
        return None

    return WatchlistEntry(
        id=row_id,
        tenant_id=tenant_id,
        chain=chain,
        address=normalized_address,
        label=label,
        created_at=created_at,
        created_by=created_by,
        alert_on_activity=alert_on_activity,
    )


def list_watchlist(tenant_id: str, db_path: Optional[str] = None) -> List[WatchlistEntry]:
    with sqlite_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, tenant_id, chain, address, label, created_at, created_by,
                   last_seen_at, last_score, alert_on_activity
            FROM watchlist
            WHERE tenant_id = ?
            ORDER BY id DESC
            """,
            (tenant_id,),
        ).fetchall()
    return [watchlist_entry_from_row(row) for row in rows]


def remove_from_watchlist(
    tenant_id: str, watchlist_id: int, db_path: Optional[str] = None
) -> bool:
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE id = ? AND tenant_id = ?",
            (watchlist_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def touch_watchlist_entry(
    tenant_id: str,
    chain: str,
    address: str,
    score: int,
    seen_at: str,
    db_path: Optional[str] = None,
) -> bool:
    with sqlite_connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE watchlist SET last_seen_at=?, last_score=?
            WHERE tenant_id=? AND chain=? AND address=?
            """,
            (seen_at, score, tenant_id, chain, address.strip().lower()),
        )
        conn.commit()
        return cursor.rowcount > 0


def is_on_watchlist(
    tenant_id: str, chain: str, address: str, db_path: Optional[str] = None
) -> Optional[WatchlistEntry]:
    with sqlite_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, tenant_id, chain, address, label, created_at, created_by,
                   last_seen_at, last_score, alert_on_activity
            FROM watchlist
            WHERE tenant_id=? AND chain=? AND address=?
            """,
            (tenant_id, chain, address.strip().lower()),
        ).fetchone()
    if not row:
        return None
    return watchlist_entry_from_row(row)
