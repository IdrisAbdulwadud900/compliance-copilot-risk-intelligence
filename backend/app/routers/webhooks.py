from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_principal
from app.authorization import require_role
from app.db import delete_webhook, list_webhooks, save_audit_log, save_webhook
from app.schemas import UserRole, WebhookConfigPayload, WebhookConfigRequest
from app.webhooks import validate_webhook_target


router = APIRouter(tags=["webhooks"])


@router.get("/webhooks", response_model=WebhookConfigPayload)
def get_webhooks(
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> WebhookConfigPayload:
    tenant_id, role, _ = principal
    require_role(role)
    items = list_webhooks(tenant_id)
    return WebhookConfigPayload(items=items)


@router.post("/webhooks")
def create_webhook(
    payload: WebhookConfigRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
):
    tenant_id, role, actor_email = principal
    require_role(role)

    try:
        validate_webhook_target(str(payload.url))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    created_at = datetime.now(timezone.utc).isoformat()
    webhook = save_webhook(
        tenant_id=tenant_id,
        url=str(payload.url),
        events=payload.events,
        created_at=created_at,
    )
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="webhook.create",
        target=str(payload.url),
        details=f"events={','.join(payload.events)}",
        created_at=created_at,
    )
    return webhook


@router.delete("/webhooks/{webhook_id}")
def remove_webhook(
    webhook_id: int,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
):
    tenant_id, role, actor_email = principal
    require_role(role)

    removed = delete_webhook(webhook_id, tenant_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    removed_at = datetime.now(timezone.utc).isoformat()
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="webhook.delete",
        target=str(webhook_id),
        details="Deleted webhook",
        created_at=removed_at,
    )
    return {"removed": True}