from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.auth import get_current_principal
from app.authorization import require_role
from app.db import (
    create_invite,
    create_user_if_not_exists,
    list_invites_by_tenant,
    list_recent_audit_logs,
    list_users_by_tenant,
    revoke_invite,
    save_audit_log,
)
from app.schemas import (
    AuditHistoryPayload,
    InviteCreateRequest,
    InviteListPayload,
    InviteResponse,
    InviteRevokeResponse,
    TeamUser,
    TeamUserCreateRequest,
    TeamUserListPayload,
    UserRole,
)


router = APIRouter(tags=["admin-team"])


@router.get("/audit-logs", response_model=AuditHistoryPayload)
def audit_logs(
    limit: int = 50,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> AuditHistoryPayload:
    tenant_id, role, _ = principal
    require_role(role, detail="Insufficient role: audit logs require admin")

    safe_limit = max(1, min(200, limit))
    items = list_recent_audit_logs(tenant_id=tenant_id, limit=safe_limit)
    return AuditHistoryPayload(items=items)


@router.get("/users", response_model=TeamUserListPayload)
def list_users(
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> TeamUserListPayload:
    tenant_id, role, _ = principal
    require_role(role, detail="Insufficient role: user listing requires admin")

    items = list_users_by_tenant(tenant_id=tenant_id)
    return TeamUserListPayload(items=items)


@router.post("/users", response_model=TeamUser)
def create_user_endpoint(
    payload: TeamUserCreateRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> TeamUser:
    tenant_id, role, actor_email = principal
    require_role(role, detail="Insufficient role: user creation requires admin")

    created_at = datetime.now(timezone.utc).isoformat()
    user = create_user_if_not_exists(
        email=payload.email,
        password=payload.password,
        tenant_id=tenant_id,
        role=payload.role,
        created_at=created_at,
    )

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="team.user.create",
        target=user.email,
        details=f"Assigned role={user.role}",
        created_at=created_at,
    )
    return user


@router.post("/users/invite", response_model=InviteResponse)
def invite_user_endpoint(
    payload: InviteCreateRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> InviteResponse:
    tenant_id, role, actor_email = principal
    require_role(role, detail="Insufficient role: invite creation requires admin")

    created_at = datetime.now(timezone.utc).isoformat()
    token, expires_at = create_invite(
        email=payload.email,
        tenant_id=tenant_id,
        role=payload.role,
        created_at=created_at,
    )
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="team.user.invite",
        target=payload.email.strip().lower(),
        details=f"Issued invite role={payload.role}",
        created_at=created_at,
    )
    return InviteResponse(
        token=token,
        email=payload.email.strip().lower(),
        role=payload.role,
        expires_at=expires_at,
    )


@router.get("/users/invites", response_model=InviteListPayload)
def list_invites_endpoint(
    limit: int = 50,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> InviteListPayload:
    tenant_id, role, _ = principal
    require_role(role, detail="Insufficient role: invite listing requires admin")

    safe_limit = max(1, min(200, limit))
    items = list_invites_by_tenant(tenant_id=tenant_id, limit=safe_limit)
    return InviteListPayload(items=items)


@router.delete("/users/invites/{token}", response_model=InviteRevokeResponse)
def revoke_invite_endpoint(
    token: str,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> InviteRevokeResponse:
    tenant_id, role, actor_email = principal
    require_role(role, detail="Insufficient role: invite revocation requires admin")

    revoked_at = datetime.now(timezone.utc).isoformat()
    revoked = revoke_invite(token=token, tenant_id=tenant_id, revoked_at=revoked_at)

    if revoked:
        save_audit_log(
            tenant_id=tenant_id,
            actor_email=actor_email,
            action="team.user.invite.revoke",
            target=token,
            details="Revoked pending invite",
            created_at=revoked_at,
        )

    return InviteRevokeResponse(token=token, revoked=revoked)