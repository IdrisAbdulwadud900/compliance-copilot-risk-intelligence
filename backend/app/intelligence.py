"""
Wallet Intelligence Engine
--------------------------
Behavior fingerprinting, narrative detection, recommended actions,
and confidence scoring. This is the "how did it know that?" layer.
"""

from typing import List, Optional, Tuple
from app.schemas import WalletInput, WalletScore, BehaviorFingerprint, WalletNarrative


# ---------------------------------------------------------------------------
# Behavior fingerprints
# A wallet can match multiple fingerprints simultaneously.
# ---------------------------------------------------------------------------

def fingerprint_wallet(wallet: WalletInput, score: WalletScore) -> List[BehaviorFingerprint]:
    """Return all behavior fingerprints that match the wallet's signal profile."""
    fingerprints: List[BehaviorFingerprint] = []

    # --- Sniper wallet ---
    # Very high txn count + high volume, almost zero exposure risk
    if (
        wallet.txn_24h > 200
        and wallet.volume_24h_usd > 200_000
        and wallet.sanctions_exposure_pct < 3
        and wallet.mixer_exposure_pct < 5
        and wallet.bridge_hops <= 1
    ):
        fingerprints.append(BehaviorFingerprint(
            label="sniper",
            display="⚡ Sniper Wallet",
            description="Extremely high-velocity, low-latency trader. Likely bot-driven entry/exit patterns consistent with memecoin sniping or MEV activity.",
            confidence=_clamp(60 + int(wallet.txn_24h / 20)),
        ))

    # --- Wash trader ---
    # Moderate-to-high volume with circular patterns (no real exposure, many txns)
    if (
        wallet.txn_24h > 100
        and wallet.volume_24h_usd > 100_000
        and wallet.mixer_exposure_pct < 8
        and wallet.sanctions_exposure_pct < 5
        and wallet.bridge_hops <= 2
    ):
        wash_confidence = _clamp(50 + int(wallet.txn_24h / 15) + int(wallet.volume_24h_usd / 50_000))
        if wash_confidence >= 55:
            fingerprints.append(BehaviorFingerprint(
                label="wash_trader",
                display="🔄 Wash Trader",
                description="Transaction volume is disproportionate to typical organic activity. Circular fund flows suggest artificial volume generation to inflate market metrics.",
                confidence=wash_confidence,
            ))

    # --- Bridge hopper ---
    # Primary signal: aggressive cross-chain movement
    if wallet.bridge_hops >= 4:
        fingerprints.append(BehaviorFingerprint(
            label="bridge_hopper",
            display="🌉 Bridge Hopper",
            description="Wallet routes funds through 4+ bridges in 24h. Classic layering pattern used to obscure fund origin across chains.",
            confidence=_clamp(55 + wallet.bridge_hops * 5),
        ))
    elif wallet.bridge_hops == 3:
        fingerprints.append(BehaviorFingerprint(
            label="bridge_hopper",
            display="🌉 Bridge Hopper",
            description="Moderate cross-chain bridge usage. Consistent with cross-chain arbitrage or early-stage layering.",
            confidence=55,
        ))

    # --- Insider wallet ---
    # High volume + very early activity relative to normal patterns + low exposure
    if (
        wallet.volume_24h_usd > 500_000
        and wallet.txn_24h < 80
        and wallet.sanctions_exposure_pct < 3
        and wallet.mixer_exposure_pct < 4
    ):
        fingerprints.append(BehaviorFingerprint(
            label="insider",
            display="🔑 Likely Insider",
            description="Large concentrated position moved in few transactions. Consistent with insider accumulation before a liquidity event or token launch.",
            confidence=_clamp(70 + int(wallet.volume_24h_usd / 200_000)),
        ))

    # --- Sanctions-linked actor ---
    if wallet.sanctions_exposure_pct >= 20:
        fingerprints.append(BehaviorFingerprint(
            label="sanctions_linked",
            display="🚫 Sanctions-Linked",
            description="Wallet has direct or indirect exposure to OFAC/UN-sanctioned addresses above critical threshold. Immediate escalation required.",
            confidence=_clamp(75 + int(wallet.sanctions_exposure_pct)),
        ))
    elif wallet.sanctions_exposure_pct >= 8:
        fingerprints.append(BehaviorFingerprint(
            label="sanctions_adjacent",
            display="⚠️ Sanctions-Adjacent",
            description="Measurable exposure to sanctioned addresses. Likely indirect through mixers or intermediary hops.",
            confidence=_clamp(55 + int(wallet.sanctions_exposure_pct * 2)),
        ))

    # --- Mixer user ---
    if wallet.mixer_exposure_pct >= 15:
        fingerprints.append(BehaviorFingerprint(
            label="mixer_user",
            display="🌀 Mixer User",
            description="Significant portion of wallet's fund flow passes through known mixers (Tornado Cash variants, Railgun, etc.). Privacy-seeking behavior at scale.",
            confidence=_clamp(65 + int(wallet.mixer_exposure_pct * 1.5)),
        ))
    elif wallet.mixer_exposure_pct >= 8:
        fingerprints.append(BehaviorFingerprint(
            label="mixer_adjacent",
            display="🌀 Mixer-Adjacent",
            description="Some exposure to mixer-linked addresses. Could be incidental or deliberate obfuscation.",
            confidence=_clamp(50 + int(wallet.mixer_exposure_pct * 2)),
        ))

    # --- Memecoin cluster participant ---
    if (
        wallet.txn_24h > 150
        and wallet.volume_24h_usd < 300_000
        and wallet.bridge_hops <= 2
        and wallet.mixer_exposure_pct < 5
        and wallet.chain in ("solana", "base", "bsc")
    ):
        fingerprints.append(BehaviorFingerprint(
            label="memecoin_cluster",
            display="🎰 Memecoin Cluster",
            description=f"High-frequency small trades on {wallet.chain.capitalize()} consistent with memecoin launch participation. Likely part of a coordinated launch or degen rotation cluster.",
            confidence=72,
        ))

    # --- Dormant whale reactivation ---
    # Very high volume in 24h, low txn count (single large moves)
    if (
        wallet.volume_24h_usd > 1_000_000
        and wallet.txn_24h <= 10
        and wallet.bridge_hops <= 1
    ):
        fingerprints.append(BehaviorFingerprint(
            label="whale_move",
            display="🐋 Whale Movement",
            description="Large single-block fund movement from a wallet with minimal transaction count. Consistent with OTC desk settlement, cold storage reactivation, or whale accumulation.",
            confidence=_clamp(68 + int(wallet.volume_24h_usd / 1_000_000) * 5),
        ))

    return fingerprints


# ---------------------------------------------------------------------------
# Narrative detection
# Produces a single human-readable contextual narrative
# ---------------------------------------------------------------------------

def detect_narrative(
    wallet: WalletInput,
    score: WalletScore,
    fingerprints: List[BehaviorFingerprint],
) -> WalletNarrative:
    """
    Given scored wallet + fingerprints, produce an intelligence narrative
    with recommended action, confidence, and business-context explanation.
    """
    labels = {f.label for f in fingerprints}
    chain = wallet.chain.capitalize()
    addr_short = wallet.address[:10] + "..."

    # --- Recommended action logic ---
    action, action_label = _recommended_action(score.score, labels)

    # --- Confidence: highest fingerprint confidence, or score-derived ---
    if fingerprints:
        confidence = max(f.confidence for f in fingerprints)
    else:
        confidence = _score_to_confidence(score.score)

    confidence = min(confidence, 97)  # Never claim 100%

    # --- Narrative copy ---
    narrative = _build_narrative(wallet, score, fingerprints, labels, chain, addr_short)

    # --- Why this matters ---
    business_context = _business_context(score, labels, chain)

    from typing import cast
    from app.schemas import RecommendedAction
    return WalletNarrative(
        summary=narrative,
        business_context=business_context,
        recommended_action=cast(RecommendedAction, action),
        recommended_action_label=action_label,
        confidence=confidence,
        fingerprint_labels=list(labels),
    )


def _recommended_action(score: int, labels: set) -> Tuple[str, str]:
    if score >= 85 or "sanctions_linked" in labels:
        return "block", "🚫 Block / Freeze"
    if score >= 65 or "mixer_user" in labels or "bridge_hopper" in labels:
        return "flag", "🚨 Flag & Escalate"
    if score >= 40 or labels & {"wash_trader", "insider", "sanctions_adjacent"}:
        return "monitor", "👁 Enhanced Monitoring"
    return "watch", "📋 Add to Watchlist"


def _build_narrative(
    wallet: WalletInput,
    score: WalletScore,
    fingerprints: List[BehaviorFingerprint],
    labels: set,
    chain: str,
    addr_short: str,
) -> str:
    if not fingerprints:
        return (
            f"Wallet {addr_short} on {chain} shows no high-confidence behavioral patterns. "
            f"Risk score {score.score}/100 — routine monitoring advised."
        )

    primary = fingerprints[0]
    parts = [primary.description]

    if len(fingerprints) > 1:
        secondary_labels = [f.display for f in fingerprints[1:3]]
        parts.append(f"Additional signals: {', '.join(secondary_labels)}.")

    if "sanctions_linked" in labels and "bridge_hopper" in labels:
        parts.append("Cross-chain layering combined with sanctions exposure is a high-confidence evasion pattern.")
    elif "insider" in labels and "memecoin_cluster" in labels:
        parts.append("This wallet may be coordinating a token launch — worth monitoring counterparties.")
    elif "wash_trader" in labels and "mixer_adjacent" in labels:
        parts.append("Combination of volume inflation and mixer proximity suggests deliberate obfuscation of trading activity.")

    return " ".join(parts)


def _business_context(score: WalletScore, labels: set, chain: str) -> str:
    if "sanctions_linked" in labels:
        return f"Processing transactions from this wallet exposes your platform to OFAC violation risk. Regulatory fines start at $50k per transaction."
    if "mixer_user" in labels:
        return f"Mixer-linked funds cannot be traced to legitimate origin. Accepting deposits from this wallet creates AML liability under FATF Travel Rule guidelines."
    if "insider" in labels:
        return f"Wallet behavior matches known pre-launch insider accumulation patterns. Interaction without due diligence creates market manipulation exposure."
    if "wash_trader" in labels:
        return f"Wash trading artificially inflates reported volume. Facilitating these transactions risks exchange delisting and regulatory scrutiny."
    if "bridge_hopper" in labels:
        return f"Multi-chain layering through {chain} bridges is a standard technique for evading chain analytics. Enhanced KYC required before onboarding."
    if "sniper" in labels:
        return "Sniper/MEV bots may negatively impact platform fairness. Monitor for front-running behavior against other users."
    if score.score >= 65:
        return "This wallet presents elevated risk that warrants compliance review before allowing further transaction processing."
    return "Standard monitoring recommended. No immediate business risk identified."


def _score_to_confidence(score: int) -> int:
    if score >= 85:
        return 88
    if score >= 65:
        return 75
    if score >= 40:
        return 62
    return 45


def _clamp(value: int, lo: int = 30, hi: int = 97) -> int:
    return max(lo, min(hi, value))
