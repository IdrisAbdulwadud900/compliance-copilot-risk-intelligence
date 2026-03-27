from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.auth import get_current_principal, get_current_role, get_current_tenant
from app.authorization import require_any_role
from app.live_wallet import enrich_wallet_input_live
from app.rate_limit import enforce_rate_limit, get_request_ip
from app.risk_engine import score_wallet
from app.schemas import Blockchain, UserRole, WalletEnrichmentResponse, WalletExplainResponse, WalletInput, WalletIntelligenceResponse, WalletScore
from app.services.intelligence_service import create_wallet_explanation, create_wallet_intelligence
from app.webhooks import fire_webhooks


router = APIRouter(tags=["intelligence"])


@router.post("/wallets/score", response_model=WalletScore)
def wallet_score(
    wallet: WalletInput,
    tenant_id: str = Depends(get_current_tenant),
    role: UserRole = Depends(get_current_role),
) -> WalletScore:
    _ = tenant_id
    _ = role
    return score_wallet(wallet)


@router.post("/wallets/explain", response_model=WalletExplainResponse)
def wallet_explain(
    wallet: WalletInput,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> WalletExplainResponse:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"), detail="Insufficient role: explain requires admin or analyst")
    return create_wallet_explanation(tenant_id, actor_email, wallet)


@router.get("/wallets/{address}/enrich", response_model=WalletEnrichmentResponse)
def wallet_enrich(
    address: str,
    chain: Blockchain = "ethereum",
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> WalletEnrichmentResponse:
    _, _, _ = principal
    try:
        return enrich_wallet_input_live(address=address, chain=chain)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Live wallet enrichment is temporarily unavailable",
        ) from exc


@router.post("/wallets/intelligence", response_model=WalletIntelligenceResponse)
def wallet_intelligence(
    wallet: WalletInput,
    request: Request,
    background_tasks: BackgroundTasks,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> WalletIntelligenceResponse:
    tenant_id, role, actor_email = principal
    require_any_role(role, ("admin", "analyst"))

    client_ip = get_request_ip(request)
    enforce_rate_limit("intelligence", f"{tenant_id}:{client_ip}")

    return create_wallet_intelligence(
        tenant_id,
        actor_email,
        wallet,
        enqueue_webhook=lambda hooks, event_name, alert: background_tasks.add_task(
            fire_webhooks,
            hooks,
            event_name,
            alert,
        ),
    )