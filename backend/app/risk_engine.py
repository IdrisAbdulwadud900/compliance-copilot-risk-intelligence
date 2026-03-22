from app.schemas import RiskLevel, WalletInput, WalletScore


CHAIN_RISK_MULTIPLIER = {
    "ethereum": 1.0,
    "arbitrum": 1.05,
    "base": 1.05,
    "polygon": 1.0,
    "bsc": 1.1,
    "solana": 0.95,
}


def _to_level(score: int) -> RiskLevel:
    if score >= 85:
        return "critical"
    if score >= 65:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def score_wallet(wallet: WalletInput) -> WalletScore:
    score = 0.0

    # weighted explainable risk model
    score += min(wallet.sanctions_exposure_pct * 0.9, 50)
    score += min(wallet.mixer_exposure_pct * 0.7, 25)
    score += min(wallet.bridge_hops * 2.5, 15)

    # velocity + size boost
    if wallet.txn_24h > 300:
        score += 6
    elif wallet.txn_24h > 120:
        score += 3

    if wallet.volume_24h_usd > 1_000_000:
        score += 8
    elif wallet.volume_24h_usd > 250_000:
        score += 4

    multiplier = CHAIN_RISK_MULTIPLIER.get(wallet.chain, 1.0)
    score *= multiplier

    score_int = max(0, min(100, round(score)))
    risk_level = _to_level(score_int)

    reason_parts = []
    if wallet.sanctions_exposure_pct >= 5:
        reason_parts.append("material sanctions exposure")
    if wallet.mixer_exposure_pct >= 10:
        reason_parts.append("notable mixer proximity")
    if wallet.bridge_hops >= 4:
        reason_parts.append("multi-bridge fund path")
    if wallet.chain in ("bsc", "arbitrum", "base") and wallet.bridge_hops >= 3:
        reason_parts.append(f"heightened {wallet.chain} bridge route risk")
    if not reason_parts:
        reason_parts.append("limited high-risk signal")

    return WalletScore(
        address=wallet.address,
        score=score_int,
        risk_level=risk_level,
        reason=", ".join(reason_parts),
    )
