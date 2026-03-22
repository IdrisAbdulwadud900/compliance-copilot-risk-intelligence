from app.risk_engine import score_wallet
from app.schemas import WalletInput


def test_high_risk_wallet_scores_high():
    wallet = WalletInput(
        address="0xAABBCCDD11223344",
        txn_24h=440,
        volume_24h_usd=2_200_000,
        sanctions_exposure_pct=28,
        mixer_exposure_pct=31,
        bridge_hops=7,
    )
    scored = score_wallet(wallet)
    assert scored.score >= 75
    assert scored.risk_level in ("high", "critical")


def test_low_risk_wallet_scores_low():
    wallet = WalletInput(
        address="0x1122AABB3344CCDD",
        txn_24h=10,
        volume_24h_usd=800,
        sanctions_exposure_pct=0,
        mixer_exposure_pct=0,
        bridge_hops=0,
    )
    scored = score_wallet(wallet)
    assert scored.score < 40
    assert scored.risk_level == "low"


def test_chain_multiplier_increases_bsc_risk_vs_ethereum():
    base = dict(
        address="0xFACEB00C11223344",
        txn_24h=150,
        volume_24h_usd=300000,
        sanctions_exposure_pct=6,
        mixer_exposure_pct=12,
        bridge_hops=3,
    )
    ethereum_wallet = WalletInput(chain="ethereum", **base)
    bsc_wallet = WalletInput(chain="bsc", **base)

    eth_scored = score_wallet(ethereum_wallet)
    bsc_scored = score_wallet(bsc_wallet)

    assert bsc_scored.score >= eth_scored.score
