from datetime import datetime, timedelta, timezone
from app.schemas import Alert


def demo_alerts() -> list[Alert]:
    now = datetime.now(timezone.utc)
    rows = [
        (
            "Potential sanctions-linked inflow",
            "critical",
            "ethereum",
            91,
            "0xA91f...D2C1",
            842_100,
            "Immediate review required",
        ),
        (
            "Mixer-adjacent transaction spike",
            "high",
            "arbitrum",
            77,
            "0x7B31...A981",
            213_440,
            "Increased obfuscation pattern",
        ),
        (
            "Cross-chain routing anomaly",
            "medium",
            "base",
            55,
            "0xF123...98B0",
            84_220,
            "Unusual bridge hop count",
        ),
        (
            "Normal treasury rebalance",
            "low",
            "solana",
            24,
            "0x11AA...9921",
            1_200_000,
            "Expected internal transfer",
        ),
    ]

    alerts = []
    for i, row in enumerate(rows, start=1):
        title, severity, chain, score, wallet, amount, summary = row
        alerts.append(
            Alert(
                id=f"alrt_{i}",
                timestamp=(now - timedelta(minutes=i * 17)).isoformat(),
            chain=chain,  # type: ignore[arg-type]
                title=title,
                severity=severity,  # type: ignore[arg-type]
                score=score,
                wallet=wallet,
                amount_usd=amount,
                summary=summary,
            )
        )
    return alerts
