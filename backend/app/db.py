import os
import sqlite3
import hashlib
import hmac
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from app.schemas import (
    AlertEvent,
    AlertTrigger,
    AnalysisEntry,
    AuditEntry,
    Blockchain,
    InviteEntry,
    InviteStatus,
    RiskLevel,
    TeamUser,
    UserRole,
    WalletInput,
    WalletScore,
    WatchlistEntry,
    WebhookConfig,
    WebhookEvent,
)


def _db_path() -> str:
    configured = os.getenv("COMPLIANCE_DB_PATH")
    if configured:
        return configured

    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "copilot.db")


def _conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or _db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL DEFAULT 'legacy',
                created_at TEXT NOT NULL,
                chain TEXT NOT NULL DEFAULT 'ethereum',
                address TEXT NOT NULL,
                txn_24h INTEGER NOT NULL,
                volume_24h_usd REAL NOT NULL,
                sanctions_exposure_pct REAL NOT NULL,
                mixer_exposure_pct REAL NOT NULL,
                bridge_hops INTEGER NOT NULL,
                score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                explanation TEXT NOT NULL
            )
            """
        )
        columns = conn.execute("PRAGMA table_info(analyses)").fetchall()
        existing_columns = {row[1] for row in columns}
        if "tenant_id" not in existing_columns:
            conn.execute(
                "ALTER TABLE analyses ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'legacy'"
            )
        if "chain" not in existing_columns:
            conn.execute(
                "ALTER TABLE analyses ADD COLUMN chain TEXT NOT NULL DEFAULT 'ethereum'"
            )
        if "tags" not in existing_columns:
            conn.execute(
                "ALTER TABLE analyses ADD COLUMN tags TEXT NOT NULL DEFAULT ''"
            )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_tenant_created ON analyses(tenant_id, created_at)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin',
                created_at TEXT NOT NULL
            )
            """
        )
        user_columns = conn.execute("PRAGMA table_info(users)").fetchall()
        existing_user_columns = {row[1] for row in user_columns}
        if "role" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'admin'")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                actor_email TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                details TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_tenant_created ON audit_logs(tenant_id, created_at)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                revoked_at TEXT
            )
            """
        )
        invite_columns = conn.execute("PRAGMA table_info(invites)").fetchall()
        existing_invite_columns = {row[1] for row in invite_columns}
        if "revoked_at" not in existing_invite_columns:
            conn.execute("ALTER TABLE invites ADD COLUMN revoked_at TEXT")

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_invites_tenant_email ON invites(tenant_id, email)"
        )

        # --- Watchlist ---
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                chain TEXT NOT NULL,
                address TEXT NOT NULL,
                label TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                last_seen_at TEXT,
                last_score INTEGER,
                alert_on_activity INTEGER NOT NULL DEFAULT 1,
                UNIQUE(tenant_id, chain, address)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_watchlist_tenant ON watchlist(tenant_id)"
        )

        # --- Alert events ---
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                trigger TEXT NOT NULL,
                chain TEXT NOT NULL,
                address TEXT NOT NULL,
                score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_events_tenant ON alert_events(tenant_id, created_at)"
        )

        # --- Webhook configs ---
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                url TEXT NOT NULL,
                events TEXT NOT NULL,
                created_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_webhooks_tenant ON webhooks(tenant_id)"
        )

        conn.commit()

    seed_default_user(db_path)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, expected = password_hash.split("$", 1)
    except ValueError:
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000
    ).hex()
    return hmac.compare_digest(digest, expected)


def create_user(
    email: str,
    password: str,
    tenant_id: str,
    role: UserRole,
    created_at: str,
    db_path: Optional[str] = None,
) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users (email, password_hash, tenant_id, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email.strip().lower(), hash_password(password), tenant_id, role, created_at),
        )
        conn.commit()


def create_user_if_not_exists(
    email: str,
    password: str,
    tenant_id: str,
    role: UserRole,
    created_at: str,
    db_path: Optional[str] = None,
) -> TeamUser:
    normalized = email.strip().lower()
    with _conn(db_path) as conn:
        existing = conn.execute(
            "SELECT id, email, tenant_id, role, created_at FROM users WHERE email = ?",
            (normalized,),
        ).fetchone()

        if existing:
            return TeamUser(
                id=existing["id"],
                email=existing["email"],
                tenant_id=existing["tenant_id"],
                role=existing["role"],
                created_at=existing["created_at"],
            )

        cursor = conn.execute(
            """
            INSERT INTO users (email, password_hash, tenant_id, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (normalized, hash_password(password), tenant_id, role, created_at),
        )
        conn.commit()

        row_id = cursor.lastrowid if cursor.lastrowid is not None else 0
        return TeamUser(
            id=row_id,
            email=normalized,
            tenant_id=tenant_id,
            role=role,
            created_at=created_at,
        )


def list_users_by_tenant(tenant_id: str, db_path: Optional[str] = None) -> List[TeamUser]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, email, tenant_id, role, created_at
            FROM users
            WHERE tenant_id = ?
            ORDER BY id DESC
            """,
            (tenant_id,),
        ).fetchall()

    return [
        TeamUser(
            id=row["id"],
            email=row["email"],
            tenant_id=row["tenant_id"],
            role=row["role"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def authenticate_user(
    email: str, password: str, db_path: Optional[str] = None
) -> Optional[Tuple[str, str, UserRole]]:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT email, password_hash, tenant_id, role FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()

    if not row:
        return None

    if not verify_password(password, row["password_hash"]):
        return None

    return row["email"], row["tenant_id"], row["role"]


def update_user_password(email: str, new_password: str, db_path: Optional[str] = None) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (hash_password(new_password), email.strip().lower()),
        )
        conn.commit()


def seed_default_user(db_path: Optional[str] = None) -> None:
    email = os.getenv("COMPLIANCE_ADMIN_EMAIL", "founder@demo.local").strip().lower()
    password = os.getenv("COMPLIANCE_ADMIN_PASSWORD", "ChangeMe123!")
    tenant_id = os.getenv("COMPLIANCE_ADMIN_TENANT", "demo-tenant").strip()
    role = os.getenv("COMPLIANCE_ADMIN_ROLE", "admin").strip().lower()
    if role not in ("admin", "analyst", "viewer"):
        role = "admin"
    created_at = os.getenv("COMPLIANCE_DEFAULT_CREATED_AT", "2026-03-21T00:00:00Z")

    with _conn(db_path) as conn:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if exists:
            return

    create_user(email, password, tenant_id, role, created_at, db_path)


def create_invite(
    email: str,
    tenant_id: str,
    role: UserRole,
    created_at: str,
    db_path: Optional[str] = None,
) -> Tuple[str, str]:
    ttl_minutes = int(os.getenv("COMPLIANCE_INVITE_TTL_MINUTES", "1440"))
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=max(1, ttl_minutes))
    ).isoformat()
    token = secrets.token_urlsafe(32)

    with _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO invites (
                token, email, tenant_id, role, created_at, expires_at, used_at, revoked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (token, email.strip().lower(), tenant_id, role, created_at, expires_at),
        )
        conn.commit()

    return token, expires_at


def consume_invite(
    token: str, accepted_at: str, db_path: Optional[str] = None
) -> Optional[Tuple[str, str, UserRole]]:
    with _conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT token, email, tenant_id, role, expires_at, used_at, revoked_at
            FROM invites
            WHERE token = ?
            """,
            (token,),
        ).fetchone()

        if not row:
            return None

        if row["used_at"] is not None:
            return None

        if row["revoked_at"] is not None:
            return None

        expires_at = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
        if expires_at < datetime.now(timezone.utc):
            return None

        conn.execute("UPDATE invites SET used_at = ? WHERE token = ?", (accepted_at, token))
        conn.commit()

    return row["email"], row["tenant_id"], row["role"]


def get_invite_status(
    token: str, db_path: Optional[str] = None
) -> Optional[Tuple[str, str, UserRole, str, InviteStatus]]:
    with _conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT token, email, role, expires_at, used_at, revoked_at
            FROM invites
            WHERE token = ?
            """,
            (token,),
        ).fetchone()

    if not row:
        return None

    return row["token"], row["email"], row["role"], row["expires_at"], _invite_status(row)


def _invite_status(row: sqlite3.Row) -> InviteStatus:
    if row["revoked_at"]:
        return "revoked"
    if row["used_at"]:
        return "used"

    expires_at = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        return "expired"

    return "active"


def list_invites_by_tenant(
    tenant_id: str, limit: int = 50, db_path: Optional[str] = None
) -> List[InviteEntry]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT token, email, tenant_id, role, created_at, expires_at, used_at, revoked_at
            FROM invites
            WHERE tenant_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (tenant_id, limit),
        ).fetchall()

    return [
        InviteEntry(
            token=row["token"],
            email=row["email"],
            tenant_id=row["tenant_id"],
            role=row["role"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            used_at=row["used_at"],
            revoked_at=row["revoked_at"],
            status=_invite_status(row),
        )
        for row in rows
    ]


def revoke_invite(
    token: str, tenant_id: str, revoked_at: str, db_path: Optional[str] = None
) -> bool:
    with _conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT used_at, revoked_at
            FROM invites
            WHERE token = ? AND tenant_id = ?
            """,
            (token, tenant_id),
        ).fetchone()

        if not row:
            return False

        if row["used_at"] is not None or row["revoked_at"] is not None:
            return False

        conn.execute(
            "UPDATE invites SET revoked_at = ? WHERE token = ? AND tenant_id = ?",
            (revoked_at, token, tenant_id),
        )
        conn.commit()
        return True


def save_audit_log(
    tenant_id: str,
    actor_email: str,
    action: str,
    target: str,
    details: str,
    created_at: str,
    db_path: Optional[str] = None,
) -> AuditEntry:
    with _conn(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO audit_logs (
                tenant_id, created_at, actor_email, action, target, details
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (tenant_id, created_at, actor_email, action, target, details),
        )
        conn.commit()
        row_id = cursor.lastrowid if cursor.lastrowid is not None else 0

    return AuditEntry(
        id=row_id,
        created_at=created_at,
        actor_email=actor_email,
        action=action,
        target=target,
        details=details,
    )


def list_recent_audit_logs(
    tenant_id: str, limit: int = 50, db_path: Optional[str] = None
) -> List[AuditEntry]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, actor_email, action, target, details
            FROM audit_logs
            WHERE tenant_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (tenant_id, limit),
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


def save_analysis(
    tenant_id: str,
    wallet: WalletInput,
    scored: WalletScore,
    explanation: str,
    created_at: str,
    db_path: Optional[str] = None,
) -> AnalysisEntry:
    with _conn(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO analyses (
                tenant_id,
                created_at, chain, address, txn_24h, volume_24h_usd,
                sanctions_exposure_pct, mixer_exposure_pct, bridge_hops,
                score, risk_level, explanation, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')
            """,
            (
                tenant_id,
                created_at,
                wallet.chain,
                wallet.address,
                wallet.txn_24h,
                wallet.volume_24h_usd,
                wallet.sanctions_exposure_pct,
                wallet.mixer_exposure_pct,
                wallet.bridge_hops,
                scored.score,
                scored.risk_level,
                explanation,
            ),
        )
        conn.commit()
        row_id = cursor.lastrowid if cursor.lastrowid is not None else 0

        return AnalysisEntry(
            id=row_id,
            created_at=created_at,
            chain=wallet.chain,
            address=wallet.address,
            score=scored.score,
            risk_level=scored.risk_level,
            explanation=explanation,
            tags=[],
        )


def list_recent_analyses(
    tenant_id: str, limit: int = 20, db_path: Optional[str] = None
) -> List[AnalysisEntry]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, chain, address, score, risk_level, explanation, tags
            FROM analyses
            WHERE tenant_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (tenant_id, limit),
        ).fetchall()

    return [
        AnalysisEntry(
            id=row["id"],
            created_at=row["created_at"],
            chain=row["chain"],
            address=row["address"],
            score=row["score"],
            risk_level=row["risk_level"],
            explanation=row["explanation"],
            tags=_parse_tags(row["tags"]),
        )
        for row in rows
    ]


def _parse_tags(raw: Optional[str]) -> List[str]:
    """Parse comma-separated tags string into a list, filtering empty strings."""
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def update_analysis_tags(
    analysis_id: int,
    tenant_id: str,
    tags: List[str],
    db_path: Optional[str] = None,
) -> Optional[AnalysisEntry]:
    """Replace tags for a specific analysis. Returns updated entry or None if not found."""
    tags_str = ",".join(t.strip() for t in tags if t.strip())
    with _conn(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE analyses SET tags = ?
            WHERE id = ? AND tenant_id = ?
            """,
            (tags_str, analysis_id, tenant_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None

        row = conn.execute(
            "SELECT id, created_at, chain, address, score, risk_level, explanation, tags FROM analyses WHERE id = ? AND tenant_id = ?",
            (analysis_id, tenant_id),
        ).fetchone()

    if not row:
        return None

    return AnalysisEntry(
        id=row["id"],
        created_at=row["created_at"],
        chain=row["chain"],
        address=row["address"],
        score=row["score"],
        risk_level=row["risk_level"],
        explanation=row["explanation"],
        tags=_parse_tags(row["tags"]),
    )


# ===========================================================================
# Watchlist
# ===========================================================================

def add_to_watchlist(
    tenant_id: str,
    chain: Blockchain,
    address: str,
    label: str,
    created_at: str,
    created_by: str,
    alert_on_activity: bool = True,
    db_path: Optional[str] = None,
) -> WatchlistEntry:
    with _conn(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO watchlist
                (tenant_id, chain, address, label, created_at, created_by, alert_on_activity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (tenant_id, chain, address.strip().lower(), label, created_at, created_by, int(alert_on_activity)),
        )
        conn.commit()
        row_id = cursor.lastrowid if cursor.lastrowid and cursor.rowcount > 0 else None

        if row_id is None:
            row = conn.execute(
                "SELECT id FROM watchlist WHERE tenant_id=? AND chain=? AND address=?",
                (tenant_id, chain, address.strip().lower()),
            ).fetchone()
            row_id = row["id"] if row else 0

    return WatchlistEntry(
        id=row_id,
        tenant_id=tenant_id,
        chain=chain,
        address=address.strip().lower(),
        label=label,
        created_at=created_at,
        created_by=created_by,
        alert_on_activity=alert_on_activity,
    )


def list_watchlist(tenant_id: str, db_path: Optional[str] = None) -> List[WatchlistEntry]:
    with _conn(db_path) as conn:
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
    return [
        WatchlistEntry(
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
        for row in rows
    ]


def remove_from_watchlist(
    tenant_id: str, watchlist_id: int, db_path: Optional[str] = None
) -> bool:
    with _conn(db_path) as conn:
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
    """Update last_seen_at and last_score for a watchlist entry. Returns True if entry found."""
    with _conn(db_path) as conn:
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
    with _conn(db_path) as conn:
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


# ===========================================================================
# Alert events
# ===========================================================================

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
    db_path: Optional[str] = None,
) -> AlertEvent:
    with _conn(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO alert_events
                (tenant_id, created_at, trigger, chain, address, score, risk_level, title, body)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tenant_id, created_at, trigger, chain, address, score, risk_level, title, body),
        )
        conn.commit()
        row_id = cursor.lastrowid if cursor.lastrowid is not None else 0
    return AlertEvent(
        id=row_id,
        tenant_id=tenant_id,
        created_at=created_at,
        trigger=trigger,
        chain=chain,
        address=address,
        score=score,
        risk_level=risk_level,
        title=title,
        body=body,
        acknowledged=False,
    )


def list_alert_events(
    tenant_id: str, limit: int = 50, unacked_only: bool = False, db_path: Optional[str] = None
) -> List[AlertEvent]:
    where = "WHERE tenant_id = ?"
    params: list = [tenant_id]
    if unacked_only:
        where += " AND acknowledged = 0"
    with _conn(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT id, tenant_id, created_at, trigger, chain, address, score,
                   risk_level, title, body, acknowledged
            FROM alert_events
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    return [
        AlertEvent(
            id=row["id"],
            tenant_id=row["tenant_id"],
            created_at=row["created_at"],
            trigger=row["trigger"],
            chain=row["chain"],
            address=row["address"],
            score=row["score"],
            risk_level=row["risk_level"],
            title=row["title"],
            body=row["body"],
            acknowledged=bool(row["acknowledged"]),
        )
        for row in rows
    ]


def acknowledge_alert(
    alert_id: int, tenant_id: str, db_path: Optional[str] = None
) -> bool:
    with _conn(db_path) as conn:
        cursor = conn.execute(
            "UPDATE alert_events SET acknowledged=1 WHERE id=? AND tenant_id=?",
            (alert_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0


# ===========================================================================
# Webhooks
# ===========================================================================

def save_webhook(
    tenant_id: str,
    url: str,
    events: List[WebhookEvent],
    created_at: str,
    db_path: Optional[str] = None,
) -> WebhookConfig:
    events_str = ",".join(events)
    with _conn(db_path) as conn:
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
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT id, tenant_id, url, events, created_at, active FROM webhooks WHERE tenant_id=? AND active=1",
            (tenant_id,),
        ).fetchall()
    return [
        WebhookConfig(
            id=row["id"],
            tenant_id=row["tenant_id"],
            url=row["url"],
            events=row["events"].split(","),
            created_at=row["created_at"],
            active=bool(row["active"]),
        )
        for row in rows
    ]


def delete_webhook(webhook_id: int, tenant_id: str, db_path: Optional[str] = None) -> bool:
    with _conn(db_path) as conn:
        cursor = conn.execute(
            "UPDATE webhooks SET active=0 WHERE id=? AND tenant_id=?",
            (webhook_id, tenant_id),
        )
        conn.commit()
        return cursor.rowcount > 0

