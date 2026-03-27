from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets
from typing import List, Optional, Tuple

from app.schemas import AuditEntry, InviteEntry, InviteStatus, TeamUser, UserRole
from app.storage.runtime import sqlite_connection


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
    with sqlite_connection(db_path) as conn:
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
    with sqlite_connection(db_path) as conn:
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


def get_user_by_email(email: str, db_path: Optional[str] = None) -> Optional[TeamUser]:
    normalized = email.strip().lower()
    with sqlite_connection(db_path) as conn:
        row = conn.execute(
            "SELECT id, email, tenant_id, role, created_at FROM users WHERE email = ?",
            (normalized,),
        ).fetchone()

    if not row:
        return None

    return TeamUser(
        id=row["id"],
        email=row["email"],
        tenant_id=row["tenant_id"],
        role=row["role"],
        created_at=row["created_at"],
    )


def list_users_by_tenant(tenant_id: str, db_path: Optional[str] = None) -> List[TeamUser]:
    with sqlite_connection(db_path) as conn:
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


def count_users(db_path: Optional[str] = None) -> int:
    with sqlite_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM users").fetchone()

    if not row:
        return 0
    return int(row["total"])


def authenticate_user(
    email: str, password: str, db_path: Optional[str] = None
) -> Optional[Tuple[str, str, UserRole]]:
    with sqlite_connection(db_path) as conn:
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
    with sqlite_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (hash_password(new_password), email.strip().lower()),
        )
        conn.commit()


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

    with sqlite_connection(db_path) as conn:
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
    with sqlite_connection(db_path) as conn:
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
    with sqlite_connection(db_path) as conn:
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

    return row["token"], row["email"], row["role"], row["expires_at"], invite_status(row)


def invite_status(row) -> InviteStatus:
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
    with sqlite_connection(db_path) as conn:
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
            status=invite_status(row),
        )
        for row in rows
    ]


def revoke_invite(
    token: str, tenant_id: str, revoked_at: str, db_path: Optional[str] = None
) -> bool:
    with sqlite_connection(db_path) as conn:
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
    with sqlite_connection(db_path) as conn:
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
    with sqlite_connection(db_path) as conn:
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