import os
import sqlite3
import hashlib
import hmac
import secrets

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from app.storage.runtime import DatabaseConnection, sqlite_connection, sqlite_db_path, sqlite_healthcheck
from app.config import INSECURE_ADMIN_PASSWORD, preview_bootstrap_enabled

from app.schemas import (
    Alert,
    AlertEvent,
    AlertSeverity,
    AlertTrigger,
    AlertType,
    AnalysisEntry,
    AuditEntry,
    Blockchain,
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
    IncidentDetail,
    IncidentStatus,
    IncidentSummary,
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
from app.repositories.auth_repository import (
    authenticate_user as repository_authenticate_user,
    count_users as repository_count_users,
    create_invite as repository_create_invite,
    create_user as repository_create_user,
    create_user_if_not_exists as repository_create_user_if_not_exists,
    get_user_by_email as repository_get_user_by_email,
    get_invite_status as repository_get_invite_status,
    hash_password as repository_hash_password,
    list_invites_by_tenant as repository_list_invites_by_tenant,
    list_recent_audit_logs as repository_list_recent_audit_logs,
    list_users_by_tenant as repository_list_users_by_tenant,
    revoke_invite as repository_revoke_invite,
    save_audit_log as repository_save_audit_log,
    update_user_password as repository_update_user_password,
    verify_password as repository_verify_password,
    consume_invite as repository_consume_invite,
)
from app.repositories.alert_repository import (
    acknowledge_alert as repository_acknowledge_alert,
    acknowledge_all_alerts as repository_acknowledge_all_alerts,
    alert_from_row as repository_alert_from_row,
    create_alert_manual as repository_create_alert_manual,
    get_alert_feed as repository_get_alert_feed,
    list_alert_events as repository_list_alert_events,
    list_alerts as repository_list_alerts,
    resolve_alert as repository_resolve_alert,
    save_alert_event as repository_save_alert_event,
)
from app.repositories.incident_repository import (
    create_incident as repository_create_incident,
    get_incident_detail as repository_get_incident_detail,
    get_incident_summary as repository_get_incident_summary,
    incident_summary_from_row as repository_incident_summary_from_row,
    link_alert_to_incident as repository_link_alert_to_incident,
    list_incidents as repository_list_incidents,
    unlink_alert_from_incident as repository_unlink_alert_from_incident,
    update_incident as repository_update_incident,
)
from app.repositories.case_repository import (
    add_case_attachment as repository_add_case_attachment,
    add_case_entity as repository_add_case_entity,
    add_case_note as repository_add_case_note,
    append_case_event as repository_append_case_event,
    create_case as repository_create_case,
    get_case_detail as repository_get_case_detail,
    get_case_summary as repository_get_case_summary,
    list_case_activity as repository_list_case_activity,
    list_case_attachments as repository_list_case_attachments,
    list_case_entities as repository_list_case_entities,
    list_case_notes as repository_list_case_notes,
    list_case_timeline as repository_list_case_timeline,
    list_cases as repository_list_cases,
    update_case as repository_update_case,
)
from app.repositories.watchlist_repository import (
    add_to_watchlist as repository_add_to_watchlist,
    is_on_watchlist as repository_is_on_watchlist,
    list_watchlist as repository_list_watchlist,
    remove_from_watchlist as repository_remove_from_watchlist,
    touch_watchlist_entry as repository_touch_watchlist_entry,
)
from app.repositories.webhook_repository import (
    delete_webhook as repository_delete_webhook,
    list_webhooks as repository_list_webhooks,
    save_webhook as repository_save_webhook,
)
from app.repositories.analysis_repository import (
    list_recent_analyses as repository_list_recent_analyses,
    save_analysis as repository_save_analysis,
    update_analysis_tags as repository_update_analysis_tags,
)
from app.migrations import apply_migrations


def _db_path() -> str:
    return sqlite_db_path()


def _conn(db_path: Optional[str] = None) -> DatabaseConnection:
    return sqlite_connection(db_path or _db_path())


def db_healthcheck(db_path: Optional[str] = None) -> bool:
    return sqlite_healthcheck(db_path)


def init_db(db_path: Optional[str] = None) -> None:
    apply_migrations(db_path)
    seed_default_user(db_path)


def hash_password(password: str) -> str:
    return repository_hash_password(password)


def verify_password(password: str, password_hash: str) -> bool:
    return repository_verify_password(password, password_hash)


def create_user(
    email: str,
    password: str,
    tenant_id: str,
    role: UserRole,
    created_at: str,
    db_path: Optional[str] = None,
) -> None:
    repository_create_user(email, password, tenant_id, role, created_at, db_path)


def create_user_if_not_exists(
    email: str,
    password: str,
    tenant_id: str,
    role: UserRole,
    created_at: str,
    db_path: Optional[str] = None,
) -> TeamUser:
    return repository_create_user_if_not_exists(email, password, tenant_id, role, created_at, db_path)


def get_user_by_email(email: str, db_path: Optional[str] = None) -> Optional[TeamUser]:
    return repository_get_user_by_email(email, db_path)


def list_users_by_tenant(tenant_id: str, db_path: Optional[str] = None) -> List[TeamUser]:
    return repository_list_users_by_tenant(tenant_id, db_path)


def count_users(db_path: Optional[str] = None) -> int:
    return repository_count_users(db_path)


def authenticate_user(
    email: str, password: str, db_path: Optional[str] = None
) -> Optional[Tuple[str, str, UserRole]]:
    return repository_authenticate_user(email, password, db_path)


def update_user_password(email: str, new_password: str, db_path: Optional[str] = None) -> None:
    repository_update_user_password(email, new_password, db_path)


def seed_default_user(db_path: Optional[str] = None) -> None:
    email = os.getenv("COMPLIANCE_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("COMPLIANCE_ADMIN_PASSWORD", "")
    tenant_id = os.getenv("COMPLIANCE_ADMIN_TENANT", "").strip()
    role = os.getenv("COMPLIANCE_ADMIN_ROLE", "admin").strip().lower()
    if not email or not password or not tenant_id:
        return
    if password == INSECURE_ADMIN_PASSWORD and not preview_bootstrap_enabled():
        return
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
    return repository_create_invite(email, tenant_id, role, created_at, db_path)


def consume_invite(
    token: str, accepted_at: str, db_path: Optional[str] = None
) -> Optional[Tuple[str, str, UserRole]]:
    return repository_consume_invite(token, accepted_at, db_path)


def get_invite_status(
    token: str, db_path: Optional[str] = None
) -> Optional[Tuple[str, str, UserRole, str, InviteStatus]]:
    return repository_get_invite_status(token, db_path)


def list_invites_by_tenant(
    tenant_id: str, limit: int = 50, db_path: Optional[str] = None
) -> List[InviteEntry]:
    return repository_list_invites_by_tenant(tenant_id, limit, db_path)


def revoke_invite(
    token: str, tenant_id: str, revoked_at: str, db_path: Optional[str] = None
) -> bool:
    return repository_revoke_invite(token, tenant_id, revoked_at, db_path)


def save_audit_log(
    tenant_id: str,
    actor_email: str,
    action: str,
    target: str,
    details: str,
    created_at: str,
    db_path: Optional[str] = None,
) -> AuditEntry:
    return repository_save_audit_log(tenant_id, actor_email, action, target, details, created_at, db_path)


def list_recent_audit_logs(
    tenant_id: str, limit: int = 50, db_path: Optional[str] = None
) -> List[AuditEntry]:
    return repository_list_recent_audit_logs(tenant_id, limit, db_path)


def save_analysis(
    tenant_id: str,
    wallet: WalletInput,
    scored: WalletScore,
    explanation: str,
    created_at: str,
    db_path: Optional[str] = None,
) -> AnalysisEntry:
    return repository_save_analysis(tenant_id, wallet, scored, explanation, created_at, db_path)


def list_recent_analyses(
    tenant_id: str, limit: int = 20, db_path: Optional[str] = None
) -> List[AnalysisEntry]:
    return repository_list_recent_analyses(tenant_id, limit, db_path)


def _parse_tags(raw: Optional[str]) -> List[str]:
    """Parse comma-separated tags string into a list, filtering empty strings."""
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _serialize_tags(tags: List[str]) -> str:
    return ",".join(tag.strip() for tag in tags if tag.strip())


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
    return repository_create_case(
        tenant_id,
        title,
        summary,
        priority,
        owner_email,
        source_type,
        source_ref,
        primary_chain,
        primary_address,
        risk_score,
        risk_level,
        tags,
        created_at,
        db_path,
    )


def list_cases(
    tenant_id: str,
    limit: int = 50,
    status: Optional[CaseStatus] = None,
    db_path: Optional[str] = None,
) -> List[CaseSummary]:
    return repository_list_cases(tenant_id, limit, status, db_path)


def get_case_summary(
    case_id: int,
    tenant_id: str,
    db_path: Optional[str] = None,
) -> Optional[CaseSummary]:
    return repository_get_case_summary(case_id, tenant_id, db_path)


def list_case_timeline(
    case_id: int,
    tenant_id: str,
    db_path: Optional[str] = None,
) -> List[CaseTimelineEvent]:
    return repository_list_case_timeline(case_id, tenant_id, db_path)


def list_case_notes(
    case_id: int,
    tenant_id: str,
    db_path: Optional[str] = None,
) -> List[CaseNote]:
    return repository_list_case_notes(case_id, tenant_id, db_path)


def list_case_entities(
    case_id: int,
    tenant_id: str,
    db_path: Optional[str] = None,
) -> List[CaseEntity]:
    return repository_list_case_entities(case_id, tenant_id, db_path)


def list_case_attachments(
    case_id: int,
    tenant_id: str,
    db_path: Optional[str] = None,
) -> List[CaseAttachment]:
    return repository_list_case_attachments(case_id, tenant_id, db_path)


def list_case_activity(
    case_id: int,
    tenant_id: str,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> List[AuditEntry]:
    return repository_list_case_activity(case_id, tenant_id, limit, db_path)


def get_case_detail(
    case_id: int,
    tenant_id: str,
    db_path: Optional[str] = None,
) -> Optional[CaseDetail]:
    return repository_get_case_detail(case_id, tenant_id, db_path)


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
    return repository_append_case_event(case_id, tenant_id, event_type, actor_email, title, body, created_at, db_path)


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
    return repository_update_case(case_id, tenant_id, updated_at, status, priority, summary, owner_email, tags, db_path)


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
    return repository_add_case_note(case_id, tenant_id, note_type, body, tags, author_email, created_at, db_path)


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
    return repository_add_case_entity(
        case_id,
        tenant_id,
        entity_type,
        label,
        chain,
        reference,
        risk_score,
        risk_level,
        created_at,
        db_path,
    )


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
    return repository_add_case_attachment(
        case_id,
        tenant_id,
        file_name,
        file_url,
        content_type,
        uploaded_by,
        created_at,
        db_path,
    )


def update_analysis_tags(
    analysis_id: int,
    tenant_id: str,
    tags: List[str],
    db_path: Optional[str] = None,
) -> Optional[AnalysisEntry]:
    return repository_update_analysis_tags(analysis_id, tenant_id, tags, db_path)


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
) -> Optional[WatchlistEntry]:
    return repository_add_to_watchlist(
        tenant_id,
        chain,
        address,
        label,
        created_at,
        created_by,
        alert_on_activity,
        db_path,
    )


def list_watchlist(tenant_id: str, db_path: Optional[str] = None) -> List[WatchlistEntry]:
    return repository_list_watchlist(tenant_id, db_path)


def remove_from_watchlist(
    tenant_id: str, watchlist_id: int, db_path: Optional[str] = None
) -> bool:
    return repository_remove_from_watchlist(tenant_id, watchlist_id, db_path)


def touch_watchlist_entry(
    tenant_id: str,
    chain: str,
    address: str,
    score: int,
    seen_at: str,
    db_path: Optional[str] = None,
) -> bool:
    return repository_touch_watchlist_entry(tenant_id, chain, address, score, seen_at, db_path)


def is_on_watchlist(
    tenant_id: str, chain: str, address: str, db_path: Optional[str] = None
) -> Optional[WatchlistEntry]:
    return repository_is_on_watchlist(tenant_id, chain, address, db_path)


# ===========================================================================
# Alert events
# ===========================================================================

def _alert_from_row(row: sqlite3.Row) -> Alert:
    return repository_alert_from_row(row)


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
    return repository_save_alert_event(
        tenant_id, trigger, chain, address, score, risk_level, title, body,
        created_at, alert_type, severity, prev_score, db_path,
    )


def list_alert_events(
    tenant_id: str, limit: int = 50, unacked_only: bool = False, db_path: Optional[str] = None
) -> List[Alert]:
    return repository_list_alert_events(tenant_id, limit, unacked_only, db_path)


def acknowledge_alert(
    alert_id: int, tenant_id: str, acked_at: Optional[str] = None, db_path: Optional[str] = None
) -> bool:
    return repository_acknowledge_alert(alert_id, tenant_id, acked_at, db_path)


def acknowledge_all_alerts(
    tenant_id: str, acked_at: str, db_path: Optional[str] = None
) -> int:
    return repository_acknowledge_all_alerts(tenant_id, acked_at, db_path)


def resolve_alert(
    alert_id: int, tenant_id: str, resolved_at: str, db_path: Optional[str] = None
) -> bool:
    return repository_resolve_alert(alert_id, tenant_id, resolved_at, db_path)


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
    return repository_create_alert_manual(
        tenant_id, alert_type, severity, chain, address, score, risk_level, title, body, created_at, db_path,
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
    return repository_list_alerts(tenant_id, limit, severity, alert_type, unacked_only, incident_id, since_id, db_path)


def get_alert_feed(
    tenant_id: str,
    since_id: int = 0,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> List[Alert]:
    return repository_get_alert_feed(tenant_id, since_id, limit, db_path)


# ===========================================================================
# Incidents
# ===========================================================================

def _incident_summary_from_row(row: sqlite3.Row) -> IncidentSummary:
    return repository_incident_summary_from_row(row)


_INCIDENT_SELECT = """
    SELECT id, tenant_id, title, description, severity, status, alert_count,
           created_at, updated_at, resolved_at, created_by
    FROM incidents
"""


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
    return repository_create_incident(tenant_id, title, description, severity, created_by, created_at, alert_ids, db_path)


def list_incidents(
    tenant_id: str,
    status: Optional[IncidentStatus] = None,
    severity: Optional[AlertSeverity] = None,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> List[IncidentSummary]:
    return repository_list_incidents(tenant_id, status, severity, limit, db_path)


def get_incident_summary(
    incident_id: int, tenant_id: str, db_path: Optional[str] = None
) -> Optional[IncidentSummary]:
    return repository_get_incident_summary(incident_id, tenant_id, db_path)


def get_incident_detail(
    incident_id: int, tenant_id: str, db_path: Optional[str] = None
) -> Optional[IncidentDetail]:
    return repository_get_incident_detail(incident_id, tenant_id, db_path)


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
    return repository_update_incident(incident_id, tenant_id, updated_at, title, description, status, severity, db_path)


def link_alert_to_incident(
    alert_id: int,
    incident_id: int,
    tenant_id: str,
    updated_at: str,
    db_path: Optional[str] = None,
) -> bool:
    return repository_link_alert_to_incident(alert_id, incident_id, tenant_id, updated_at, db_path)


def unlink_alert_from_incident(
    alert_id: int,
    incident_id: int,
    tenant_id: str,
    updated_at: str,
    db_path: Optional[str] = None,
) -> bool:
    return repository_unlink_alert_from_incident(alert_id, incident_id, tenant_id, updated_at, db_path)


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
    return repository_save_webhook(tenant_id, url, events, created_at, db_path)


def list_webhooks(tenant_id: str, db_path: Optional[str] = None) -> List[WebhookConfig]:
    return repository_list_webhooks(tenant_id, db_path)


def delete_webhook(webhook_id: int, tenant_id: str, db_path: Optional[str] = None) -> bool:
    return repository_delete_webhook(webhook_id, tenant_id, db_path)

