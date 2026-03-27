from app.intelligence import detect_narrative, fingerprint_wallet
from app.risk_engine import score_wallet
from app.schemas import WalletInput


def test_fingerprint_wallet_returns_fallback_for_active_wallet_without_other_signals():
    wallet = WalletInput(
        chain="ethereum",
        address="0x1111111111111111111111111111111111111111",
        txn_24h=12,
        volume_24h_usd=1500,
        sanctions_exposure_pct=0,
        mixer_exposure_pct=0,
        bridge_hops=0,
    )

    fingerprints = fingerprint_wallet(wallet, score_wallet(wallet))

    assert len(fingerprints) >= 1
    assert fingerprints[0].label == "active_wallet"


def test_low_score_bridge_hopper_is_monitored_not_flagged():
    wallet = WalletInput(
        chain="arbitrum",
        address="0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        txn_24h=8,
        volume_24h_usd=12_500,
        sanctions_exposure_pct=0,
        mixer_exposure_pct=0,
        bridge_hops=3,
    )

    scored = score_wallet(wallet)
    fingerprints = fingerprint_wallet(wallet, scored)
    narrative = detect_narrative(wallet, scored, fingerprints)

    assert scored.risk_level == "low"
    assert scored.score < 40
    assert "bridge_hopper" in {fingerprint.label for fingerprint in fingerprints}
    assert narrative.recommended_action == "monitor"