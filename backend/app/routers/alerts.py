import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.auth import get_current_principal
from app.authorization import require_any_role
from app.db import (
    acknowledge_alert,
    acknowledge_all_alerts as db_acknowledge_all_alerts,
    create_alert_manual,
    get_alert_feed,
    link_alert_to_incident,
    list_alert_events,
    list_alerts,
    resolve_alert,
    save_audit_log,
)
from app.schemas import (
    Alert,
    AlertEventPayload,
    AlertFeedPayload,
    AlertSeverity,
    AlertType,
    CreateAlertRequest,
    UpdateAlertRequest,
    UserRole,
)


router = APIRouter(tags=["alerts"])


@router.get("/alert-events", response_model=AlertEventPayload)
def get_alert_events(
    limit: int = 50,
    unacked_only: bool = False,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> AlertEventPayload:
    tenant_id, _, _ = principal
    safe_limit = max(1, min(200, limit))
    items = list_alert_events(tenant_id=tenant_id, limit=safe_limit, unacked_only=unacked_only)
    unread = sum(1 for alert in items if not alert.acknowledged)
    return AlertEventPayload(items=items, unread_count=unread)


@router.post("/alert-events/{alert_id}/ack")
def ack_alert_event(
    alert_id: int,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> dict[str, bool]:
    tenant_id, _, actor_email = principal
    acked_at = datetime.now(timezone.utc).isoformat()
    ok = acknowledge_alert(alert_id, tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="alert.ack",
        target=str(alert_id),
        details="Acknowledged alert event",
        created_at=acked_at,
    )
    return {"acknowledged": True}


@router.get("/alerts", response_model=AlertFeedPayload)
def get_alerts(
    limit: int = 50,
    severity: Optional[AlertSeverity] = None,
    alert_type: Optional[AlertType] = None,
    unacked_only: bool = False,
    incident_id: Optional[int] = None,
    since_id: int = 0,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> AlertFeedPayload:
    tenant_id, _, _ = principal
    safe_limit = max(1, min(200, limit))
    items = list_alerts(
        tenant_id=tenant_id,
        limit=safe_limit,
        severity=severity,
        alert_type=alert_type,
        unacked_only=unacked_only,
        incident_id=incident_id,
        since_id=since_id,
    )
    unread = sum(1 for alert in items if not alert.acknowledged)
    last_id = max((alert.id for alert in items), default=since_id)
    return AlertFeedPayload(items=items, unread_count=unread, last_id=last_id)


@router.post("/alerts", response_model=Alert)
def create_alert_endpoint(
    payload: CreateAlertRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> Alert:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    created_at = datetime.now(timezone.utc).isoformat()
    alert = create_alert_manual(
        tenant_id=tenant_id,
        alert_type=payload.alert_type,
        severity=payload.severity,
        chain=payload.chain,
        address=payload.address,
        score=payload.score,
        risk_level=payload.risk_level,
        title=payload.title,
        body=payload.body,
        created_at=created_at,
    )
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="alert.create",
        target=payload.address,
        details=f"type={payload.alert_type} severity={payload.severity}",
        created_at=created_at,
    )
    return alert


@router.get("/alerts/feed", response_model=AlertFeedPayload)
def get_alerts_feed(
    since_id: int = 0,
    limit: int = 50,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> AlertFeedPayload:
    tenant_id, _, _ = principal
    safe_limit = max(1, min(200, limit))
    items = get_alert_feed(tenant_id=tenant_id, since_id=since_id, limit=safe_limit)
    unread = sum(1 for alert in items if not alert.acknowledged)
    last_id = max((alert.id for alert in items), default=since_id)
    return AlertFeedPayload(items=items, unread_count=unread, last_id=last_id)


@router.get("/alerts/stream")
async def alerts_stream(
    since_id: int = 0,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
):
    tenant_id, _, _ = principal
    cursor = since_id

    async def event_gen():
        nonlocal cursor
        yield 'data: {"type":"connected"}\n\n'
        while True:
            items = get_alert_feed(tenant_id=tenant_id, since_id=cursor, limit=50)
            for alert in items:
                yield f"data: {alert.model_dump_json()}\n\n"
                cursor = max(cursor, alert.id)
            await asyncio.sleep(3)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/alerts/{alert_id}/ack")
def ack_alert(
    alert_id: int,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> dict[str, object]:
    tenant_id, _, actor_email = principal
    acked_at = datetime.now(timezone.utc).isoformat()
    ok = acknowledge_alert(alert_id, tenant_id, acked_at)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="alert.ack",
        target=str(alert_id),
        details="Acknowledged alert",
        created_at=acked_at,
    )
    return {"acknowledged": True, "alert_id": alert_id}


@router.post("/alerts/ack-all")
def ack_all_alerts_endpoint(
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> dict[str, int]:
    tenant_id, _, actor_email = principal
    acked_at = datetime.now(timezone.utc).isoformat()
    count = db_acknowledge_all_alerts(tenant_id, acked_at)
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="alert.ack_all",
        target="alerts",
        details=f"Acknowledged {count} alert(s)",
        created_at=acked_at,
    )
    return {"acked": count}


@router.patch("/alerts/{alert_id}")
def update_alert_endpoint(
    alert_id: int,
    payload: UpdateAlertRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> dict[str, object]:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    updated_at = datetime.now(timezone.utc).isoformat()

    if payload.resolved is True:
        ok = resolve_alert(alert_id, tenant_id, updated_at)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
        save_audit_log(
            tenant_id=tenant_id,
            actor_email=actor_email,
            action="alert.resolve",
            target=str(alert_id),
            details="Resolved alert",
            created_at=updated_at,
        )

    if payload.incident_id is not None:
        linked = link_alert_to_incident(alert_id, payload.incident_id, tenant_id, updated_at)
        if not linked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert or incident not found",
            )
        save_audit_log(
            tenant_id=tenant_id,
            actor_email=actor_email,
            action="alert.link_incident",
            target=str(alert_id),
            details=f"Linked to incident {payload.incident_id}",
            created_at=updated_at,
        )

    return {"updated": True, "alert_id": alert_id}