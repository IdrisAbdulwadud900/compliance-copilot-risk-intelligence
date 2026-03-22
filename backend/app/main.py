from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from typing import cast

from app.ai_explainer import explain_alert
from app.auth import get_current_principal, get_current_role, get_current_tenant, login_and_issue_token
from app.db import init_db, list_recent_analyses, list_recent_audit_logs, save_analysis, save_audit_log, update_analysis_tags
from app.db import create_user_if_not_exists, list_users_by_tenant
from app.db import (
    authenticate_user,
    consume_invite,
    create_invite,
    get_invite_status,
    list_invites_by_tenant,
    revoke_invite,
    update_user_password,
)
from app.db import (
    add_to_watchlist,
    list_watchlist,
    remove_from_watchlist,
    is_on_watchlist,
    touch_watchlist_entry,
    save_alert_event,
    list_alert_events,
    acknowledge_alert,
    save_webhook,
    list_webhooks,
    delete_webhook,
)
from app.intelligence import fingerprint_wallet, detect_narrative
from app.cluster import build_cluster
from app.webhooks import fire_webhooks
from app.risk_engine import score_wallet
from app.rate_limit import enforce_rate_limit, get_request_ip
from app.sample_data import demo_alerts
from app.schemas import (
    AuditHistoryPayload,
    AcceptInviteRequest,
    AnalysisEntry,
    AnalysisHistoryPayload,
    DashboardPayload,
    InviteCreateRequest,
    InviteListPayload,
    InvitePublicStatusResponse,
    InviteRevokeResponse,
    InviteResponse,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    TagUpdateRequest,
    UserRole,
    TeamUser,
    TeamUserCreateRequest,
    TeamUserListPayload,
    Blockchain,
    WalletExplainResponse,
    WalletInput,
    WalletScore,
    WalletIntelligenceResponse,
    WatchlistAddRequest,
    WatchlistPayload,
    AlertEventPayload,
    AlertAckRequest,
    WebhookConfigRequest,
    WebhookConfigPayload,
    WalletClusterResponse,
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Crypto Compliance Copilot API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
def auth_login(payload: LoginRequest, request: Request) -> LoginResponse:
    client_ip = get_request_ip(request)
    enforce_rate_limit("auth", f"login:{client_ip}")

    result = login_and_issue_token(payload.email, payload.password)
    if not result:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token, email, tenant_id, role = result
    created_at = datetime.now(timezone.utc).isoformat()
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=email,
        action="auth.login",
        target="session",
        details=f"User logged in with role={role}",
        created_at=created_at,
    )
    return LoginResponse(access_token=token, tenant_id=tenant_id, email=email, role=role)


@app.post("/auth/accept-invite", response_model=LoginResponse)
def auth_accept_invite(payload: AcceptInviteRequest, request: Request) -> LoginResponse:
    client_ip = get_request_ip(request)
    enforce_rate_limit("auth", f"accept_invite:{client_ip}")

    accepted_at = datetime.now(timezone.utc).isoformat()
    consumed = consume_invite(payload.token, accepted_at)
    if not consumed:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite")

    email, tenant_id, role = consumed
    user = create_user_if_not_exists(
        email=email,
        password=payload.password,
        tenant_id=tenant_id,
        role=role,
        created_at=accepted_at,
    )
    update_user_password(user.email, payload.password)

    token, login_email, login_tenant, login_role = login_and_issue_token(user.email, payload.password) or (
        "",
        "",
        "",
        "viewer",
    )
    if not token:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invite acceptance failed")

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=login_email,
        action="auth.accept_invite",
        target="session",
        details=f"Accepted invite as role={login_role}",
        created_at=accepted_at,
    )
    return LoginResponse(
        access_token=token,
        tenant_id=login_tenant,
        email=login_email,
        role=login_role,
    )


@app.get("/auth/invite-status", response_model=InvitePublicStatusResponse)
def auth_invite_status(token: str, request: Request) -> InvitePublicStatusResponse:
    client_ip = get_request_ip(request)
    enforce_rate_limit("invite_status", client_ip)

    status_info = get_invite_status(token)
    if not status_info:
        return InvitePublicStatusResponse(token=token, status="expired")

    invite_token, email, role, expires_at, status = status_info
    return InvitePublicStatusResponse(
        token=invite_token,
        status=status,
        email=email,
        role=role,
        expires_at=expires_at,
    )


@app.post("/auth/change-password")
def auth_change_password(
    payload: PasswordChangeRequest,
    request: Request,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> dict[str, str]:
    tenant_id, _, actor_email = principal
    client_ip = get_request_ip(request)
    enforce_rate_limit("auth", f"change_password:{client_ip}")

    if actor_email == "api-key-user":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password change requires user session token",
        )

    authed = authenticate_user(actor_email, payload.current_password)
    if not authed:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

    update_user_password(actor_email, payload.new_password)
    changed_at = datetime.now(timezone.utc).isoformat()
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="auth.change_password",
        target=actor_email,
        details="User changed own password",
        created_at=changed_at,
    )
    return {"status": "ok"}


@app.get("/dashboard", response_model=DashboardPayload)
def dashboard(tenant_id: str = Depends(get_current_tenant)) -> DashboardPayload:
    analyses = list_recent_analyses(tenant_id=tenant_id, limit=100)
    alerts = []
    for entry in analyses[:20]:
        alerts.append(
            {
                "id": f"analysis_{entry.id}",
                "timestamp": entry.created_at,
                "chain": entry.chain,
                "title": f"{entry.chain.capitalize()} wallet risk analysis",
                "severity": entry.risk_level,
                "score": entry.score,
                "wallet": entry.address,
                "amount_usd": 0,
                "summary": entry.explanation,
            }
        )

    if not alerts:
        alerts = demo_alerts()

    total = len(analyses)
    critical = len([a for a in analyses if a.risk_level == "critical"])
    avg_score = round(sum(a.score for a in analyses) / total, 1) if total > 0 else 0.0

    return DashboardPayload(
        total_wallets_monitored=len({a.address for a in analyses}) if analyses else 0,
        alerts_today=min(total, 100),
        critical_alerts_today=critical,
        avg_risk_score=avg_score,
        trend_7d=[12, 14, 11, 16, 19, 17, 23],
        alerts=alerts,
    )


@app.post("/wallets/score", response_model=WalletScore)
def wallet_score(
    wallet: WalletInput,
    tenant_id: str = Depends(get_current_tenant),
    role: UserRole = Depends(get_current_role),
) -> WalletScore:
    _ = tenant_id
    _ = role
    return score_wallet(wallet)


@app.post("/wallets/explain")
def wallet_explain(
    wallet: WalletInput,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> WalletExplainResponse:
    tenant_id, role, actor_email = principal
    if role not in ("admin", "analyst"):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role: explain requires admin or analyst",
        )

    scored = score_wallet(wallet)
    explanation = explain_alert(scored, wallet)
    created_at = datetime.now(timezone.utc).isoformat()
    saved = save_analysis(tenant_id, wallet, scored, explanation, created_at)
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="analysis.explain",
        target=wallet.address,
        details=f"Score={saved.score} level={saved.risk_level}",
        created_at=created_at,
    )
    return WalletExplainResponse(
        analysis_id=saved.id,
        chain=saved.chain,
        address=saved.address,
        score=saved.score,
        risk_level=saved.risk_level,
        explanation=saved.explanation,
    )


@app.get("/analyses", response_model=AnalysisHistoryPayload)
def analyses(
    limit: int = 20, tenant_id: str = Depends(get_current_tenant)
) -> AnalysisHistoryPayload:
    safe_limit = max(1, min(100, limit))
    items = list_recent_analyses(tenant_id=tenant_id, limit=safe_limit)
    return AnalysisHistoryPayload(items=items)


@app.patch("/analyses/{analysis_id}/tags", response_model=AnalysisEntry)
def patch_analysis_tags(
    analysis_id: int,
    payload: TagUpdateRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> AnalysisEntry:
    tenant_id, role, actor_email = principal
    if role not in ("admin", "analyst"):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role: tagging requires admin or analyst",
        )

    sanitized = [t[:32] for t in payload.tags[:10] if t.strip()]
    updated = update_analysis_tags(analysis_id, tenant_id, sanitized)
    if not updated:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    updated_at = datetime.now(timezone.utc).isoformat()
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="analysis.tag",
        target=str(analysis_id),
        details=f"Tags set to: {', '.join(sanitized) or 'none'}",
        created_at=updated_at,
    )
    return updated


@app.get("/analyses/export")
def export_analyses_csv(
    limit: int = 500,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
):
    from fastapi.responses import StreamingResponse
    import csv
    import io

    tenant_id, role, _ = principal
    if role not in ("admin", "analyst"):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role: export requires admin or analyst",
        )

    safe_limit = max(1, min(1000, limit))
    items = list_recent_analyses(tenant_id=tenant_id, limit=safe_limit)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "created_at", "chain", "address", "score", "risk_level", "tags", "explanation"])
    for entry in items:
        writer.writerow([
            entry.id,
            entry.created_at,
            entry.chain,
            entry.address,
            entry.score,
            entry.risk_level,
            "|".join(entry.tags),
            entry.explanation,
        ])
    output.seek(0)

    filename = f"compliance_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/audit-logs", response_model=AuditHistoryPayload)
def audit_logs(
    limit: int = 50,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> AuditHistoryPayload:
    tenant_id, role, _ = principal
    if role != "admin":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role: audit logs require admin",
        )

    safe_limit = max(1, min(200, limit))
    items = list_recent_audit_logs(tenant_id=tenant_id, limit=safe_limit)
    return AuditHistoryPayload(items=items)


@app.get("/users", response_model=TeamUserListPayload)
def list_users(
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> TeamUserListPayload:
    tenant_id, role, _ = principal
    if role != "admin":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role: user listing requires admin",
        )

    items = list_users_by_tenant(tenant_id=tenant_id)
    return TeamUserListPayload(items=items)


@app.post("/users", response_model=TeamUser)
def create_user_endpoint(
    payload: TeamUserCreateRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> TeamUser:
    tenant_id, role, actor_email = principal
    if role != "admin":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role: user creation requires admin",
        )

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


@app.post("/users/invite", response_model=InviteResponse)
def invite_user_endpoint(
    payload: InviteCreateRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> InviteResponse:
    tenant_id, role, actor_email = principal
    if role != "admin":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role: invite creation requires admin",
        )

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


@app.get("/users/invites", response_model=InviteListPayload)
def list_invites_endpoint(
    limit: int = 50,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> InviteListPayload:
    tenant_id, role, _ = principal
    if role != "admin":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role: invite listing requires admin",
        )

    safe_limit = max(1, min(200, limit))
    items = list_invites_by_tenant(tenant_id=tenant_id, limit=safe_limit)
    return InviteListPayload(items=items)


@app.delete("/users/invites/{token}", response_model=InviteRevokeResponse)
def revoke_invite_endpoint(
    token: str,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> InviteRevokeResponse:
    tenant_id, role, actor_email = principal
    if role != "admin":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role: invite revocation requires admin",
        )

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


# ─── Intelligence ────────────────────────────────────────────────────────────

@app.post("/wallets/intelligence", response_model=WalletIntelligenceResponse)
def wallet_intelligence(
    wallet: WalletInput,
    request: Request,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> WalletIntelligenceResponse:
    tenant_id, role, actor_email = principal
    if role not in ("admin", "analyst"):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    client_ip = get_request_ip(request)
    enforce_rate_limit("intelligence", f"{tenant_id}:{client_ip}")

    scored = score_wallet(wallet)
    explanation = explain_alert(scored, wallet)
    fingerprints = fingerprint_wallet(wallet, scored)
    narrative = detect_narrative(wallet, scored, fingerprints)

    created_at = datetime.now(timezone.utc).isoformat()
    saved = save_analysis(tenant_id, wallet, scored, explanation, created_at)

    # watchlist hit check — fire alert if watched
    watched = is_on_watchlist(tenant_id, wallet.chain, wallet.address)
    if watched:
        touch_watchlist_entry(tenant_id, wallet.chain, wallet.address, scored.score, created_at)
        if scored.score >= 40:
            alert = save_alert_event(
                tenant_id=tenant_id,
                trigger="watchlist_activity",
                chain=wallet.chain,
                address=wallet.address,
                score=scored.score,
                risk_level=scored.risk_level,
                title=f"Watchlist hit: {wallet.address[:10]}…",
                body=f"Score {scored.score} ({scored.risk_level}). {narrative.summary}",
                created_at=created_at,
            )
            hooks = list_webhooks(tenant_id)
            fire_webhooks(hooks, "alert.fired", alert)

    # auto-alert on critical scores even if not on watchlist
    if scored.score >= 85 and not watched:
        alert = save_alert_event(
            tenant_id=tenant_id,
            trigger="score_threshold",
            chain=wallet.chain,
            address=wallet.address,
            score=scored.score,
            risk_level=scored.risk_level,
            title=f"Critical score: {wallet.address[:10]}… ({scored.score})",
            body=f"{narrative.summary} Recommended: {narrative.recommended_action_label}.",
            created_at=created_at,
        )
        hooks = list_webhooks(tenant_id)
        fire_webhooks(hooks, "wallet.flagged", alert)

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="analysis.intelligence",
        target=wallet.address,
        details=f"Score={saved.score} action={narrative.recommended_action} confidence={narrative.confidence:.0%}",
        created_at=created_at,
    )
    return WalletIntelligenceResponse(
        analysis_id=saved.id,
        chain=saved.chain,
        address=saved.address,
        score=saved.score,
        risk_level=saved.risk_level,
        explanation=saved.explanation,
        fingerprints=fingerprints,
        narrative=narrative,
    )


@app.get("/wallets/{address}/cluster", response_model=WalletClusterResponse)
def wallet_cluster(
    address: str,
    chain: str = "ethereum",
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> WalletClusterResponse:
    tenant_id, role, _ = principal
    if role not in ("admin", "analyst"):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    from app.schemas import WalletInput as WI
    # validate chain
    valid_chains = ["ethereum", "solana", "arbitrum", "base", "bsc", "polygon"]
    if chain not in valid_chains:
        chain = "ethereum"
    chain_value = cast(Blockchain, chain)

    dummy_wallet = WI(
        address=address,
        chain=chain_value,
        txn_24h=0,
        volume_24h_usd=0,
        sanctions_exposure_pct=0,
        mixer_exposure_pct=0,
        bridge_hops=0,
    )
    scored = score_wallet(dummy_wallet)
    return build_cluster(dummy_wallet, scored.score)


# ─── Watchlist ────────────────────────────────────────────────────────────────

@app.get("/watchlist", response_model=WatchlistPayload)
def get_watchlist(
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> WatchlistPayload:
    tenant_id, _, _ = principal
    items = list_watchlist(tenant_id)
    return WatchlistPayload(items=items)


@app.post("/watchlist")
def add_watchlist_entry(
    payload: WatchlistAddRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
):
    tenant_id, role, actor_email = principal
    if role not in ("admin", "analyst"):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

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
        from fastapi import HTTPException, status
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


@app.delete("/watchlist/{entry_id}")
def remove_watchlist_entry(
    entry_id: int,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
):
    tenant_id, role, actor_email = principal
    if role not in ("admin", "analyst"):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    removed = remove_from_watchlist(tenant_id, entry_id)
    if not removed:
        from fastapi import HTTPException, status
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


# ─── Alert Events ─────────────────────────────────────────────────────────────

@app.get("/alert-events", response_model=AlertEventPayload)
def get_alert_events(
    limit: int = 50,
    unacked_only: bool = False,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> AlertEventPayload:
    tenant_id, _, _ = principal
    safe_limit = max(1, min(200, limit))
    items = list_alert_events(tenant_id=tenant_id, limit=safe_limit, unacked_only=unacked_only)
    unread = sum(1 for a in items if not a.acknowledged)
    return AlertEventPayload(items=items, unread_count=unread)


@app.post("/alert-events/{alert_id}/ack")
def ack_alert_event(
    alert_id: int,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
):
    tenant_id, _, actor_email = principal
    acked_at = datetime.now(timezone.utc).isoformat()
    ok = acknowledge_alert(alert_id, tenant_id)
    if not ok:
        from fastapi import HTTPException, status
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


# ─── Webhooks ─────────────────────────────────────────────────────────────────

@app.get("/webhooks", response_model=WebhookConfigPayload)
def get_webhooks(
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> WebhookConfigPayload:
    tenant_id, role, _ = principal
    if role != "admin":
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    items = list_webhooks(tenant_id)
    return WebhookConfigPayload(items=items)


@app.post("/webhooks")
def create_webhook(
    payload: WebhookConfigRequest,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
):
    tenant_id, role, actor_email = principal
    if role != "admin":
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    created_at = datetime.now(timezone.utc).isoformat()
    webhook = save_webhook(
        tenant_id=tenant_id,
        url=payload.url,
        events=payload.events,
        created_at=created_at,
    )
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="webhook.create",
        target=payload.url,
        details=f"events={','.join(payload.events)}",
        created_at=created_at,
    )
    return webhook


@app.delete("/webhooks/{webhook_id}")
def remove_webhook(
    webhook_id: int,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
):
    tenant_id, role, actor_email = principal
    if role != "admin":
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    removed = delete_webhook(webhook_id, tenant_id)
    if not removed:
        from fastapi import HTTPException, status
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
