from datetime import datetime, timezone
from typing import Callable, Optional

import app.alert_engine as alert_engine
from app.ai_explainer import explain_alert
from app.db import (
    is_on_watchlist,
    list_webhooks,
    save_alert_event,
    save_analysis,
    save_audit_log,
    touch_watchlist_entry,
)
from app.intelligence import detect_narrative, fingerprint_wallet
from app.risk_engine import score_wallet
from app.schemas import Alert, WalletExplainResponse, WalletInput, WalletIntelligenceResponse
from app.webhooks import fire_webhooks


def create_wallet_explanation(
    tenant_id: str,
    actor_email: str,
    wallet: WalletInput,
) -> WalletExplainResponse:
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


def create_wallet_intelligence(
    tenant_id: str,
    actor_email: str,
    wallet: WalletInput,
    enqueue_webhook: Optional[Callable[[list, str, Alert], None]] = None,
) -> WalletIntelligenceResponse:
    scored = score_wallet(wallet)
    explanation = explain_alert(scored, wallet)
    fingerprints = fingerprint_wallet(wallet, scored)
    narrative = detect_narrative(wallet, scored, fingerprints)

    created_at = datetime.now(timezone.utc).isoformat()
    saved = save_analysis(tenant_id, wallet, scored, explanation, created_at)

    watched_entry = is_on_watchlist(tenant_id, wallet.chain, wallet.address)
    watched = watched_entry is not None
    if watched:
        touch_watchlist_entry(tenant_id, wallet.chain, wallet.address, scored.score, created_at)

    alert_candidates = alert_engine.evaluate_wallet_alerts(
        wallet=wallet,
        scored=scored,
        is_watchlist=watched,
        narrative_summary=narrative.summary,
        recommended_action=narrative.recommended_action,
    )
    if alert_candidates:
        hooks = list_webhooks(tenant_id)
        enqueue = enqueue_webhook or (lambda webhook_list, event_name, alert: fire_webhooks(webhook_list, event_name, alert))
        for candidate in alert_candidates:
            fired_alert = save_alert_event(
                tenant_id=tenant_id,
                trigger=candidate.trigger,
                chain=wallet.chain,
                address=wallet.address,
                score=scored.score,
                risk_level=scored.risk_level,
                title=candidate.title,
                body=candidate.body,
                created_at=created_at,
                alert_type=candidate.alert_type,
                severity=candidate.severity,
                prev_score=candidate.prev_score,
            )
            webhook_event = "alert.fired" if candidate.alert_type == "watchlist_hit" else "wallet.flagged"
            enqueue(hooks, webhook_event, fired_alert)

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