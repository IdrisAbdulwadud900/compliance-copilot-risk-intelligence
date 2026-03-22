from app.schemas import WalletInput, WalletScore


def explain_alert(score: WalletScore, wallet: WalletInput) -> str:
    chain_context = wallet.chain.capitalize()
    if score.risk_level in ("critical", "high"):
        return (
            f"High urgency on {chain_context}: wallet {score.address[:10]}... scored {score.score}/100 "
            f"due to {score.reason}. Review source of funds and consider temporary hold."
        )
    if score.risk_level == "medium":
        return (
            f"Medium risk on {chain_context}: wallet {score.address[:10]}... scored {score.score}/100 "
            f"from {score.reason}. Keep under enhanced monitoring."
        )
    return (
        f"Low risk on {chain_context}: wallet {score.address[:10]}... scored {score.score}/100 with "
        f"{score.reason}. No immediate action needed."
    )
