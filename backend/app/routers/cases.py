from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_principal
from app.authorization import require_any_role
from app.db import (
    add_case_attachment,
    add_case_entity,
    add_case_note,
    append_case_event,
    create_case,
    get_case_detail,
    list_cases,
    save_audit_log,
    update_case,
)
from app.schemas import (
    CaseAttachment,
    CaseDetail,
    CaseEntity,
    CaseListPayload,
    CaseNote,
    CaseStatus,
    CreateCaseAttachmentRequest,
    CreateCaseEntityRequest,
    CreateCaseNoteRequest,
    CreateCaseRequest,
    UpdateCaseRequest,
    UserRole,
)


router = APIRouter(tags=["cases"])


@router.get("/cases", response_model=CaseListPayload)
def get_cases(
    limit: int = 50,
    status_value: Optional[CaseStatus] = Query(default=None, alias="status"),
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> CaseListPayload:
    tenant_id, _, _ = principal
    safe_limit = max(1, min(200, limit))
    items = list_cases(tenant_id=tenant_id, limit=safe_limit, status=status_value)
    return CaseListPayload(items=items)


@router.post("/cases", response_model=CaseDetail)
def create_case_endpoint(
    payload: CreateCaseRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> CaseDetail:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    created_at = datetime.now(timezone.utc).isoformat()
    case = create_case(
        tenant_id=tenant_id,
        title=payload.title,
        summary=payload.summary,
        priority=payload.priority,
        owner_email=payload.owner_email or actor_email,
        source_type=payload.source_type,
        source_ref=payload.source_ref,
        primary_chain=payload.primary_chain,
        primary_address=payload.primary_address,
        risk_score=payload.risk_score,
        risk_level=payload.risk_level,
        tags=payload.tags,
        created_at=created_at,
    )

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="case.create",
        target=f"case:{case.id}",
        details=f"title={case.title} priority={case.priority} risk={case.risk_level}:{case.risk_score}",
        created_at=created_at,
    )

    detail = get_case_detail(case.id, tenant_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load created case",
        )
    return detail


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case_endpoint(
    case_id: int,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> CaseDetail:
    tenant_id, _, _ = principal
    detail = get_case_detail(case_id, tenant_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return detail


@router.patch("/cases/{case_id}", response_model=CaseDetail)
def update_case_endpoint(
    case_id: int,
    payload: UpdateCaseRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> CaseDetail:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    updated_at = datetime.now(timezone.utc).isoformat()
    updated = update_case(
        case_id=case_id,
        tenant_id=tenant_id,
        updated_at=updated_at,
        status=payload.status,
        priority=payload.priority,
        summary=payload.summary,
        owner_email=payload.owner_email,
        tags=payload.tags,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    if payload.status is not None:
        append_case_event(
            case_id=case_id,
            tenant_id=tenant_id,
            event_type="status_changed",
            actor_email=actor_email,
            title="Status updated",
            body=f"Case moved to {payload.status.replace('_', ' ')}.",
            created_at=updated_at,
        )

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="case.update",
        target=f"case:{case_id}",
        details="Updated case metadata",
        created_at=updated_at,
    )

    detail = get_case_detail(case_id, tenant_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load updated case",
        )
    return detail


@router.post("/cases/{case_id}/notes", response_model=CaseNote)
def add_case_note_endpoint(
    case_id: int,
    payload: CreateCaseNoteRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> CaseNote:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    created_at = datetime.now(timezone.utc).isoformat()
    note = add_case_note(
        case_id=case_id,
        tenant_id=tenant_id,
        note_type=payload.note_type,
        body=payload.body,
        tags=payload.tags,
        author_email=actor_email,
        created_at=created_at,
    )
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    append_case_event(
        case_id=case_id,
        tenant_id=tenant_id,
        event_type="note_added",
        actor_email=actor_email,
        title="New note added",
        body=payload.body[:180],
        created_at=created_at,
    )
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="case.note.add",
        target=f"case:{case_id}",
        details=f"type={payload.note_type}",
        created_at=created_at,
    )
    return note


@router.post("/cases/{case_id}/entities", response_model=CaseEntity)
def add_case_entity_endpoint(
    case_id: int,
    payload: CreateCaseEntityRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> CaseEntity:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    created_at = datetime.now(timezone.utc).isoformat()
    entity = add_case_entity(
        case_id=case_id,
        tenant_id=tenant_id,
        entity_type=payload.entity_type,
        label=payload.label,
        chain=payload.chain,
        reference=payload.reference,
        risk_score=payload.risk_score,
        risk_level=payload.risk_level,
        created_at=created_at,
    )
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    event_type = (
        "wallet_linked"
        if payload.entity_type == "wallet"
        else "cluster_linked"
        if payload.entity_type == "cluster"
        else "analysis_linked"
        if payload.entity_type == "analysis"
        else "alert_linked"
    )
    append_case_event(
        case_id=case_id,
        tenant_id=tenant_id,
        event_type=event_type,
        actor_email=actor_email,
        title=f"Linked {payload.entity_type}",
        body=f"{payload.label} · {payload.reference}",
        created_at=created_at,
    )
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="case.entity.add",
        target=f"case:{case_id}",
        details=f"type={payload.entity_type} reference={payload.reference}",
        created_at=created_at,
    )
    return entity


@router.post("/cases/{case_id}/attachments", response_model=CaseAttachment)
def add_case_attachment_endpoint(
    case_id: int,
    payload: CreateCaseAttachmentRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> CaseAttachment:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role")

    created_at = datetime.now(timezone.utc).isoformat()
    attachment = add_case_attachment(
        case_id=case_id,
        tenant_id=tenant_id,
        file_name=payload.file_name,
        file_url=str(payload.file_url),
        content_type=payload.content_type,
        uploaded_by=actor_email,
        created_at=created_at,
    )
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    append_case_event(
        case_id=case_id,
        tenant_id=tenant_id,
        event_type="attachment_added",
        actor_email=actor_email,
        title="Evidence attached",
        body=f"{payload.file_name} ({payload.content_type})",
        created_at=created_at,
    )
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="case.attachment.add",
        target=f"case:{case_id}",
        details=f"file={payload.file_name}",
        created_at=created_at,
    )
    return attachment