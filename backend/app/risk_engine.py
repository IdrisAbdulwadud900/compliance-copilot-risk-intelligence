"""risk_engine.py — Production-grade wallet risk scoring engine.

Architecture
────────────
  score_wallet(WalletInput) → WalletScore
      │
      ├── _rule_sanctions(pct)           → ScoreComponent
      ├── _rule_mixer(pct)               → ScoreComponent
      ├── _rule_bridge(hops, chain)      → ScoreComponent
      ├── _rule_velocity(txn_24h)        → ScoreComponent
      └── _rule_volume(volume_usd)       → ScoreComponent
              │
              ╰── sum(c.value) × chain_multiplier → clamped int [0, 100]
                      │
                      ╰── non-empty c.label per component → reason string

Each rule is an isolated, independently testable function that returns a
``ScoreComponent``.  Explanations are derived *exclusively* from the labels on
those components, so they always reflect what actually moved the score.

Adding or tuning a rule never touches the aggregation logic.

Performance
───────────
``_score_params()`` is decorated with ``@lru_cache``.  ``score_wallet()``
unpacks the Pydantic model to hashable primitives and delegates entirely to the
cached function.  The wallet *address* is excluded from the cache key because
the score is derived from on-chain signals, not the identifier.

Scalability notes
─────────────────
* For multi-worker deployments replace ``lru_cache`` with a Redis-backed
  ``TTLCache`` (e.g. ``cachetools.TTLCache`` + a distributed lock).
* For bulk scoring, call ``score_wallet()`` via ``asyncio.to_thread`` or a
  ``concurrent.futures.ThreadPoolExecutor``; the computation is CPU-bound and
  GIL-friendly.
* Weights and thresholds should be promoted to a versioned config store
  (database row or YAML) to allow hot-reload without redeployment.  Expose the
  active ``scoring_version`` on ``WalletScore`` so downstream consumers can
  detect model changes.
* Tiered boosts (velocity, volume) are intentional step functions for
  auditability; replace with continuous log-scale functions if smoother
  gradients are preferred.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Final, Sequence

from app.schemas import RiskLevel, WalletInput, WalletScore

logger = logging.getLogger(__name__)


# ── Weights and per-component caps ────────────────────────────────────────────

SANCTIONS_WEIGHT: Final[float] = 0.9
SANCTIONS_CAP:    Final[float] = 50.0

MIXER_WEIGHT: Final[float] = 0.7
MIXER_CAP:    Final[float] = 25.0

BRIDGE_WEIGHT_PER_HOP: Final[float] = 2.5
BRIDGE_CAP:            Final[float] = 15.0

# Velocity tiers: (min_txns_exclusive, score_boost). Must be descending.
_TXN_TIERS: Final[tuple[tuple[int, float], ...]] = (
    (300, 6.0),
    (120, 3.0),
)

# Volume tiers: (min_usd_exclusive, score_boost). Must be descending.
_VOL_TIERS: Final[tuple[tuple[float, float], ...]] = (
    (1_000_000.0, 8.0),
    (250_000.0,   4.0),
)


# ── Chain configuration ───────────────────────────────────────────────────────

CHAIN_RISK_MULTIPLIER: Final[dict[str, float]] = {
    "ethereum": 1.0,
    "arbitrum": 1.05,
    "base":     1.05,
    "polygon":  1.0,
    "bsc":      1.1,
    "solana":   0.95,
}
_DEFAULT_CHAIN_MULTIPLIER: Final[float] = 1.0

# Chains that warrant a chain-specific bridge narrative in the reason string.
# NOTE: the numeric penalty is already handled by CHAIN_RISK_MULTIPLIER; this
# set controls only the explanation label so analysts see why the chain matters.
_BRIDGE_RISK_CHAINS: Final[frozenset[str]] = frozenset({"bsc", "arbitrum", "base"})
_BRIDGE_RISK_MIN_HOPS: Final[int] = 3


# ── Risk-level thresholds ─────────────────────────────────────────────────────

_CRITICAL_THRESHOLD: Final[int] = 85
_HIGH_THRESHOLD:     Final[int] = 65
_MEDIUM_THRESHOLD:   Final[int] = 40


# ── Score component ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScoreComponent:
    """An isolated, auditable unit of the risk score.

    Attributes:
        name:  Machine-readable rule identifier.
        raw:   Contribution before the per-component cap is applied.
        value: Contribution added to the running total (raw, capped).
        label: Human-readable explanation fragment included in the final
               ``reason`` string.  Empty string when the component is silent.
    """

    name:  str
    raw:   float
    value: float
    label: str

    @property
    def is_silent(self) -> bool:
        """True when this component neither scores nor explains anything."""
        return self.value == 0.0 and not self.label


# ── Private helpers ───────────────────────────────────────────────────────────

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _to_level(score: int) -> RiskLevel:
    if score >= _CRITICAL_THRESHOLD:
        return "critical"
    if score >= _HIGH_THRESHOLD:
        return "high"
    if score >= _MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def _first_matching_tier(
    value: float,
    tiers: Sequence[tuple[float, float]],
) -> float:
    """Return the boost for the first tier whose threshold ``value`` exceeds.

    Tiers must be ordered from highest threshold to lowest so the most
    significant match is returned.
    """
    for threshold, boost in tiers:
        if value > threshold:
            return boost
    return 0.0


# ── Scoring rules ─────────────────────────────────────────────────────────────

def _rule_sanctions(sanctions_pct: float) -> ScoreComponent:
    """Sanctions-list exposure contributes up to SANCTIONS_CAP points."""
    raw   = sanctions_pct * SANCTIONS_WEIGHT
    value = _clamp(raw, 0.0, SANCTIONS_CAP)
    label = "material sanctions exposure" if value > 0 else ""
    return ScoreComponent("sanctions", raw, value, label)


def _rule_mixer(mixer_pct: float) -> ScoreComponent:
    """Mixer/tumbler proximity contributes up to MIXER_CAP points."""
    raw   = mixer_pct * MIXER_WEIGHT
    value = _clamp(raw, 0.0, MIXER_CAP)
    label = "notable mixer proximity" if value > 0 else ""
    return ScoreComponent("mixer", raw, value, label)


def _rule_bridge(bridge_hops: int, chain: str) -> ScoreComponent:
    """Bridge-hop depth contributes up to BRIDGE_CAP points.

    When the wallet is on a high-bridge-risk chain and meets the minimum hop
    threshold, the explanation label is enriched with the chain name.  The
    numeric penalty is already applied via CHAIN_RISK_MULTIPLIER; no extra
    score is added here to avoid double-counting.
    """
    raw   = bridge_hops * BRIDGE_WEIGHT_PER_HOP
    value = _clamp(raw, 0.0, BRIDGE_CAP)

    if value == 0.0:
        label = ""
    elif chain in _BRIDGE_RISK_CHAINS and bridge_hops >= _BRIDGE_RISK_MIN_HOPS:
        label = f"multi-bridge fund path with heightened {chain} route risk"
    else:
        label = "multi-bridge fund path"

    return ScoreComponent("bridge", raw, value, label)


def _rule_velocity(txn_24h: int) -> ScoreComponent:
    """High transaction velocity adds a flat boost from the tier table."""
    boost = _first_matching_tier(float(txn_24h), _TXN_TIERS)
    label = f"high transaction velocity ({txn_24h} txns/24 h)" if boost > 0 else ""
    return ScoreComponent("velocity", boost, boost, label)


def _rule_volume(volume_usd: float) -> ScoreComponent:
    """Elevated 24-hour volume adds a flat boost from the tier table."""
    boost = _first_matching_tier(volume_usd, _VOL_TIERS)
    label = f"elevated 24 h volume (${volume_usd:,.0f})" if boost > 0 else ""
    return ScoreComponent("volume", boost, boost, label)


# ── Aggregation and cache ─────────────────────────────────────────────────────

@lru_cache(maxsize=2048)
def _score_params(
    chain: str,
    txn_24h: int,
    volume_24h_usd: float,
    sanctions_exposure_pct: float,
    mixer_exposure_pct: float,
    bridge_hops: int,
) -> tuple[int, str]:
    """Pure, fully deterministic computation — safe to cache indefinitely.

    The wallet *address* is deliberately excluded from the cache key because
    the score is derived entirely from on-chain signals, not the identifier.
    Two wallets with the same exposure profile receive the same score, and the
    cache hit avoids redundant arithmetic.

    Returns:
        (score_int, reason_str)
    """
    if chain not in CHAIN_RISK_MULTIPLIER:
        logger.warning(
            "Unknown chain %r passed to risk engine — using default multiplier %.2f",
            chain,
            _DEFAULT_CHAIN_MULTIPLIER,
        )

    components: tuple[ScoreComponent, ...] = (
        _rule_sanctions(sanctions_exposure_pct),
        _rule_mixer(mixer_exposure_pct),
        _rule_bridge(bridge_hops, chain),
        _rule_velocity(txn_24h),
        _rule_volume(volume_24h_usd),
    )

    raw_sum    = sum(c.value for c in components)
    multiplier = CHAIN_RISK_MULTIPLIER.get(chain, _DEFAULT_CHAIN_MULTIPLIER)
    score_int  = int(_clamp(round(raw_sum * multiplier)))

    labels = [c.label for c in components if c.label]
    reason = ", ".join(labels) if labels else "limited high-risk signal"

    return score_int, reason


# ── Public API ────────────────────────────────────────────────────────────────

def score_wallet(wallet: WalletInput) -> WalletScore:
    """Score a wallet and return a fully annotated :class:`~app.schemas.WalletScore`.

    This function is intentionally thin: it unpacks the Pydantic model to
    hashable primitives and delegates all computation to ``_score_params``,
    which is LRU-cached.
    """
    score_int, reason = _score_params(
        wallet.chain,
        wallet.txn_24h,
        wallet.volume_24h_usd,
        wallet.sanctions_exposure_pct,
        wallet.mixer_exposure_pct,
        wallet.bridge_hops,
    )
    return WalletScore(
        address=wallet.address,
        score=score_int,
        risk_level=_to_level(score_int),
        reason=reason,
    )
