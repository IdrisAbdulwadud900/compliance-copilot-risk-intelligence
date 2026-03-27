from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_principal
from app.authorization import require_any_role
from app.db import add_to_watchlist, list_watchlist, remove_from_watchlist, save_audit_log
from app.schemas import UserRole, WatchlistAddRequest, WatchlistPayload


router = APIRouter(tags=["watchlist"])


@router.get("/watchlist", response_model=WatchlistPayload)
def get_watchlist(
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> WatchlistPayload:
    tenant_id, _, _ = principal
    items = list_watchlist(tenant_id)
    return WatchlistPayload(items=items)


@router.post("/watchlist")
def add_watchlist_entry(
    payload: WatchlistAddRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
):
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    created_at = datetime.now(timezone.utc).isoformat()
    entry = add_to_watchlist(
        tenant_id=tenant_id,
        chain=payload.chain,
        address=payload.address,
        label=payload.label,
        created_by=actor_email,
        alert_on_activity=payload.alert_on_activity,
        created_at=created_at,
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already on watchlist")

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="watchlist.add",
        target=payload.address,
        details=f"chain={payload.chain} label={payload.label or ''}",
        created_at=created_at,
    )
    return entry


@router.delete("/watchlist/{entry_id}")
def remove_watchlist_entry(
    entry_id: int,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> dict[str, bool]:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    removed = remove_from_watchlist(tenant_id, entry_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    removed_at = datetime.now(timezone.utc).isoformat()
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="watchlist.remove",
        target=str(entry_id),
        details="Removed watchlist entry",
        created_at=removed_at,
    )
    return {"removed": True}