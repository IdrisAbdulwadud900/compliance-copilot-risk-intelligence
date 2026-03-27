from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_principal
from app.authorization import require_any_role
from app.db import (
    create_incident,
    get_incident_detail,
    link_alert_to_incident,
    list_incidents,
    save_audit_log,
    unlink_alert_from_incident,
    update_incident,
)
from app.schemas import (
    AlertSeverity,
    CreateIncidentRequest,
    IncidentDetail,
    IncidentListPayload,
    IncidentStatus,
    IncidentSummary,
    LinkAlertToIncidentRequest,
    UpdateIncidentRequest,
    UserRole,
)


router = APIRouter(tags=["incidents"])


@router.get("/incidents", response_model=IncidentListPayload)
def get_incidents(
    limit: int = 50,
    status_value: Optional[IncidentStatus] = Query(default=None, alias="status"),
    severity: Optional[AlertSeverity] = None,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> IncidentListPayload:
    tenant_id, _, _ = principal
    safe_limit = max(1, min(200, limit))
    items = list_incidents(
        tenant_id=tenant_id,
        status=status_value,
        severity=severity,
        limit=safe_limit,
    )
    return IncidentListPayload(items=items)


@router.post("/incidents", response_model=IncidentDetail)
def create_incident_endpoint(
    payload: CreateIncidentRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> IncidentDetail:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    created_at = datetime.now(timezone.utc).isoformat()
    summary = create_incident(
        tenant_id=tenant_id,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        created_by=actor_email,
        created_at=created_at,
        alert_ids=payload.alert_ids,
    )
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="incident.create",
        target=f"incident:{summary.id}",
        details=f"title={payload.title} severity={payload.severity} alerts={payload.alert_ids}",
        created_at=created_at,
    )
    detail = get_incident_detail(summary.id, tenant_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load incident",
        )
    return detail


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
def get_incident_endpoint(
    incident_id: int,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> IncidentDetail:
    tenant_id, _, _ = principal
    detail = get_incident_detail(incident_id, tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return detail


@router.patch("/incidents/{incident_id}", response_model=IncidentSummary)
def update_incident_endpoint(
    incident_id: int,
    payload: UpdateIncidentRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> IncidentSummary:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    updated_at = datetime.now(timezone.utc).isoformat()
    updated = update_incident(
        incident_id=incident_id,
        tenant_id=tenant_id,
        updated_at=updated_at,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        severity=payload.severity,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="incident.update",
        target=f"incident:{incident_id}",
        details=f"status={payload.status} severity={payload.severity}",
        created_at=updated_at,
    )
    return updated


@router.post("/incidents/{incident_id}/alerts")
def link_alerts_to_incident_endpoint(
    incident_id: int,
    payload: LinkAlertToIncidentRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> dict[str, int]:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    updated_at = datetime.now(timezone.utc).isoformat()
    linked_count = sum(
        1 for alert_id in payload.alert_ids
        if link_alert_to_incident(alert_id, incident_id, tenant_id, updated_at)
    )
    if linked_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid alerts found or incident not found",
        )

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="incident.alerts.link",
        target=f"incident:{incident_id}",
        details=f"Linked {linked_count} alert(s): {payload.alert_ids}",
        created_at=updated_at,
    )
    return {"linked": linked_count, "incident_id": incident_id}


@router.delete("/incidents/{incident_id}/alerts/{alert_id}")
def unlink_alert_from_incident_endpoint(
    incident_id: int,
    alert_id: int,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> dict[str, object]:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    updated_at = datetime.now(timezone.utc).isoformat()
    ok = unlink_alert_from_incident(alert_id, incident_id, tenant_id, updated_at)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not linked to this incident",
        )

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="incident.alerts.unlink",
        target=f"incident:{incident_id}",
        details=f"Unlinked alert {alert_id}",
        created_at=updated_at,
    )
    return {"unlinked": True, "alert_id": alert_id}