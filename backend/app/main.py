from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from typing import Optional, cast

from app.auth import get_current_principal, get_current_role, get_current_tenant
from app.config import allowed_origins, config_warnings, database_runtime_summary, validate_runtime_config
from app.db import init_db, list_recent_analyses, save_audit_log, update_analysis_tags
from app.cluster import build_cluster
from app.migrations import migration_status_summary
from app.observability import install_request_tracing
from app.risk_engine import score_wallet
from app.rate_limit import enforce_rate_limit, get_request_ip, reset_rate_limits
from app.routers.admin_team import router as admin_team_router
from app.routers.alerts import router as alerts_router
from app.routers.auth import router as auth_router
from app.routers.cases import router as cases_router
from app.routers.incidents import router as incidents_router
from app.routers.intelligence import router as intelligence_router
from app.routers.watchlist import router as watchlist_router
from app.routers.webhooks import router as webhooks_router
from app.schemas import (
    AnalysisEntry,
    AnalysisHistoryPayload,
    DashboardPayload,
    TagUpdateRequest,
    UserRole,
    Blockchain,
    WalletExplainResponse,
    WalletInput,
    WalletScore,
    WalletIntelligenceResponse,
    WalletClusterResponse,
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_config()
    reset_rate_limits()
    init_db()
    yield


app = FastAPI(title="Crypto Compliance Copilot API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins()),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_request_tracing(app)
app.include_router(admin_team_router)
app.include_router(alerts_router)
app.include_router(auth_router)
app.include_router(cases_router)
app.include_router(incidents_router)
app.include_router(intelligence_router)
app.include_router(watchlist_router)
app.include_router(webhooks_router)

@app.get("/")
def root() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "crypto-compliance-copilot-api",
        "version": app.version,
        "message": "Compliance Copilot backend is running.",
        "docs_url": app.docs_url,
        "openapi_url": app.openapi_url,
        "health_url": "/health",
        "ready_url": "/ready",
    }


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "crypto-compliance-copilot-api",
        "version": app.version,
        "database": database_runtime_summary(),
        "migrations": migration_status_summary(),
        "warnings": config_warnings(),
    }


@app.get("/ready")
def ready() -> dict[str, object]:
    from app.db import db_healthcheck

    db_ok = db_healthcheck()
    status_value = "ok" if db_ok else "degraded"
    return {
        "status": status_value,
        "service": "crypto-compliance-copilot-api",
        "version": app.version,
        "checks": {
            "database": "ok" if db_ok else "error",
            "config": "ok" if not config_warnings() else "warning",
        },
        "database": database_runtime_summary(),
        "migrations": migration_status_summary(),
        "warnings": config_warnings(),
    }


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


@app.get("/wallets/{address}/cluster", response_model=WalletClusterResponse)
def wallet_cluster(
    address: str,
    chain: str = "ethereum",
    txn_24h: int = 0,
    volume_24h_usd: float = 0,
    sanctions_exposure_pct: float = 0,
    mixer_exposure_pct: float = 0,
    bridge_hops: int = 0,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> WalletClusterResponse:
    tenant_id, role, _ = principal
    if role not in ("admin", "analyst"):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    from app.live_cluster import build_live_cluster
    from app.live_wallet import enrich_wallet_input_live
    from app.schemas import WalletInput as WI
    # validate chain
    valid_chains = ["ethereum", "solana", "arbitrum", "base", "bsc", "polygon"]
    if chain not in valid_chains:
        chain = "ethereum"
    chain_value = cast(Blockchain, chain)

    dummy_wallet = WI(
        address=address,
        chain=chain_value,
        txn_24h=max(0, txn_24h),
        volume_24h_usd=max(0, volume_24h_usd),
        sanctions_exposure_pct=min(100.0, max(0.0, sanctions_exposure_pct)),
        mixer_exposure_pct=min(100.0, max(0.0, mixer_exposure_pct)),
        bridge_hops=max(0, bridge_hops),
    )

    cluster_wallet = dummy_wallet
    if (
        chain_value == "ethereum"
        and txn_24h == 0
        and volume_24h_usd == 0
        and sanctions_exposure_pct == 0
        and mixer_exposure_pct == 0
        and bridge_hops == 0
    ):
        try:
            enriched = enrich_wallet_input_live(address=address, chain=chain_value)
            cluster_wallet = WI(
                address=enriched.address,
                chain=enriched.chain,
                txn_24h=enriched.txn_24h,
                volume_24h_usd=enriched.volume_24h_usd,
                sanctions_exposure_pct=enriched.sanctions_exposure_pct,
                mixer_exposure_pct=enriched.mixer_exposure_pct,
                bridge_hops=enriched.bridge_hops,
            )
        except Exception:
            cluster_wallet = dummy_wallet

    scored = score_wallet(cluster_wallet)
    try:
        live_cluster = build_live_cluster(cluster_wallet, scored.score)
        if live_cluster is not None:
            return live_cluster
    except Exception:
        pass

    return build_cluster(cluster_wallet, scored.score)


