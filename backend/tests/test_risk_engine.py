"""Tests for the production risk engine.

Covers:
  - end-to-end scoring behaviour (high / low risk, chain multiplier)
  - individual rule functions in isolation
  - explanation accuracy: labels come only from components that scored
  - LRU cache consistency
  - address-agnosticism of the score
  - edge cases: zero inputs, caps, tier boundaries
"""

import pytest

from app.risk_engine import (
    _rule_bridge,
    _rule_mixer,
    _rule_sanctions,
    _rule_velocity,
    _rule_volume,
    _score_params,
    _to_level,
    score_wallet,
)
from app.schemas import WalletInput


# ── End-to-end scoring ────────────────────────────────────────────────────────

def test_high_risk_wallet_scores_high():
    wallet = WalletInput(
        address="0xaabbccdd11223344aabbccdd11223344aabbccdd",
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
        address="0x1122aabb3344ccdd1122aabb3344ccdd1122aabb",
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
        address="0xfaceb00c11223344faceb00c11223344faceb00c",
        txn_24h=150,
        volume_24h_usd=300000,
        sanctions_exposure_pct=6,
        mixer_exposure_pct=12,
        bridge_hops=3,
    )
    eth_scored = score_wallet(WalletInput(chain="ethereum", **base))
    bsc_scored = score_wallet(WalletInput(chain="bsc", **base))

    assert bsc_scored.score >= eth_scored.score


# ── Explanation accuracy ──────────────────────────────────────────────────────

def test_explanation_matches_score_components():
    """Every non-zero signal must produce a matching explanation fragment."""
    wallet = WalletInput(
        address="0xEXPLAIN00001122",
        txn_24h=150,
        volume_24h_usd=300_000,
        sanctions_exposure_pct=6,
        mixer_exposure_pct=12,
        bridge_hops=3,
        chain="bsc",
    )
    reason = score_wallet(wallet).reason

    assert "sanctions" in reason
    assert "mixer" in reason
    assert "bridge" in reason
    assert "velocity" in reason
    assert "volume" in reason


def test_zero_signals_return_fallback_reason():
    wallet = WalletInput(
        address="0xZERO0000AAAABBBB",
        txn_24h=0,
        volume_24h_usd=0,
        sanctions_exposure_pct=0,
        mixer_exposure_pct=0,
        bridge_hops=0,
    )
    assert score_wallet(wallet).reason == "limited high-risk signal"


def test_bsc_bridge_reason_mentions_chain_name():
    """Bridge label for a risk chain should call out the chain explicitly."""
    wallet = WalletInput(
        address="0xBSCBRIDGEAAABBBB",
        txn_24h=0,
        volume_24h_usd=0,
        sanctions_exposure_pct=0,
        mixer_exposure_pct=0,
        bridge_hops=5,
        chain="bsc",
    )
    assert "bsc" in score_wallet(wallet).reason


def test_ethereum_bridge_reason_does_not_mention_chain():
    """Ethereum is not a bridge-risk chain; the label should be generic."""
    wallet = WalletInput(
        address="0xETHBRIDGEAABBCCDD",
        txn_24h=0,
        volume_24h_usd=0,
        sanctions_exposure_pct=0,
        mixer_exposure_pct=0,
        bridge_hops=5,
        chain="ethereum",
    )
    reason = score_wallet(wallet).reason
    assert "bridge" in reason
    assert "ethereum" not in reason


# ── Individual rule functions ─────────────────────────────────────────────────

def test_rule_sanctions_weight_and_cap():
    assert _rule_sanctions(0).value == 0.0
    assert _rule_sanctions(10).value == pytest.approx(9.0)   # 10 × 0.9
    assert _rule_sanctions(100).value == 50.0                # capped


def test_rule_sanctions_label_only_when_nonzero():
    assert _rule_sanctions(0).label == ""
    assert _rule_sanctions(0.1).label != ""


def test_rule_mixer_weight_and_cap():
    assert _rule_mixer(0).value == 0.0
    assert _rule_mixer(10).value == pytest.approx(7.0)       # 10 × 0.7
    assert _rule_mixer(100).value == 25.0                    # capped


def test_rule_bridge_weight_and_cap():
    assert _rule_bridge(0, "ethereum").value == 0.0
    assert _rule_bridge(1, "ethereum").value == pytest.approx(2.5)
    assert _rule_bridge(6, "ethereum").value == 15.0         # capped at 15


def test_rule_bridge_label_variants():
    assert _rule_bridge(0, "bsc").label == ""
    assert "bsc" in _rule_bridge(3, "bsc").label             # chain risk threshold met
    assert "bsc" not in _rule_bridge(2, "bsc").label         # below threshold → generic
    assert "arbitrum" in _rule_bridge(3, "arbitrum").label
    assert "heightened" not in _rule_bridge(3, "ethereum").label


def test_rule_velocity_tiers():
    assert _rule_velocity(0).value == 0.0
    assert _rule_velocity(120).value == 0.0   # exactly at boundary → no boost
    assert _rule_velocity(121).value == 3.0
    assert _rule_velocity(300).value == 3.0   # exactly at boundary → lower tier
    assert _rule_velocity(301).value == 6.0


def test_rule_volume_tiers():
    assert _rule_volume(0).value == 0.0
    assert _rule_volume(250_000).value == 0.0    # exactly at boundary → no boost
    assert _rule_volume(250_001).value == 4.0
    assert _rule_volume(1_000_000).value == 4.0  # exactly at boundary → lower tier
    assert _rule_volume(1_000_001).value == 8.0


# ── Risk-level thresholds ─────────────────────────────────────────────────────

@pytest.mark.parametrize("score,expected", [
    (0,   "low"),
    (39,  "low"),
    (40,  "medium"),
    (64,  "medium"),
    (65,  "high"),
    (84,  "high"),
    (85,  "critical"),
    (100, "critical"),
])
def test_to_level_boundaries(score, expected):
    assert _to_level(score) == expected


# ── Cache behaviour ───────────────────────────────────────────────────────────

def test_cache_returns_same_object_for_identical_inputs():
    """LRU cache must return the *same* tuple object on repeated calls."""
    args = ("ethereum", 200, 500_000.0, 10.0, 5.0, 2)
    assert _score_params(*args) is _score_params(*args)


def test_score_is_address_agnostic():
    """Two wallets with identical signals but different addresses must score the same."""
    base = dict(
        txn_24h=50,
        volume_24h_usd=10_000,
        sanctions_exposure_pct=5,
        mixer_exposure_pct=5,
        bridge_hops=1,
        chain="ethereum",
    )
    w1 = score_wallet(WalletInput(address="0xAAAAAAAA11111111", **base))
    w2 = score_wallet(WalletInput(address="0xBBBBBBBB22222222", **base))

    assert w1.score == w2.score
    assert w1.risk_level == w2.risk_level
    assert w1.reason == w2.reason
