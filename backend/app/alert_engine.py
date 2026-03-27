"""
Alert generation engine
-----------------------
Evaluates wallet activity and risk changes to produce AlertCandidate objects
that callers should persist (via db.save_alert_event) and fire to webhooks.

Thresholds (tunable via module-level constants)
-----------------------------------------------
* SCORE_THRESHOLD_CRITICAL  – 85  : non-watchlist wallet → score_threshold alert
* SCORE_THRESHOLD_WATCHLIST – 40  : watched wallet → watchlist_hit alert
* SCORE_THRESHOLD_HIGH      – 65  : watched wallet → additional score_threshold alert
* RISK_CHANGE_MIN_DELTA     – 15  : minimum point shift to fire a risk_change alert
* VOLUME_SPIKE_USD          – 500_000 : 24-h volume threshold for volume_spike alert
* TXN_SPIKE_COUNT           – 500     : 24-h txn count threshold for volume_spike alert

Priority / deduplication rules
-------------------------------
1. watchlist_hit   – fired if wallet is watched AND score ≥ SCORE_THRESHOLD_WATCHLIST
2. score_threshold – fired if:
     • non-watchlist wallet AND score ≥ SCORE_THRESHOLD_CRITICAL, OR
     • watched wallet AND score ≥ SCORE_THRESHOLD_HIGH
3. risk_change     – fired when |Δscore vs prev_score| ≥ RISK_CHANGE_MIN_DELTA
4. volume_spike    – fired on high volume/txn count, ONLY when no higher-priority
                     alert (score_threshold / watchlist_hit) was already fired
"""

from __future__ import annotations

from typing import Optional

from app.schemas import (
    AlertSeverity,
    AlertTrigger,
    AlertType,
    RiskLevel,
    WalletInput,
    WalletScore,
)

# ── Tunable thresholds ────────────────────────────────────────────────────────
SCORE_THRESHOLD_CRITICAL: int = 85   # fire score_threshold for un-watched wallets
SCORE_THRESHOLD_HIGH: int = 65       # fire score_threshold for watched wallets too
SCORE_THRESHOLD_WATCHLIST: int = 40  # fire watchlist_hit
RISK_CHANGE_MIN_DELTA: int = 15      # minimum absolute score delta for risk_change
VOLUME_SPIKE_USD: float = 500_000.0  # USD 24-h volume for volume_spike
TXN_SPIKE_COUNT: int = 500           # transaction count 24-h for volume_spike

# ── Severity mapping ──────────────────────────────────────────────────────────
_RISK_TO_SEVERITY: dict[str, AlertSeverity] = {
    "low": "info",
    "medium": "warning",
    "high": "high",
    "critical": "critical",
}


def risk_to_severity(risk_level: RiskLevel) -> AlertSeverity:
    return _RISK_TO_SEVERITY.get(risk_level, "warning")  # type: ignore[return-value]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _short(address: str, n: int = 10) -> str:
    return f"{address[:n]}…" if len(address) > n else address


# ── Title / body builders ─────────────────────────────────────────────────────
def _score_threshold_text(
    wallet: WalletInput,
    scored: WalletScore,
    narrative_summary: str,
    recommended_action: str,
) -> tuple[str, str, AlertSeverity]:
    title = f"Critical score: {_short(wallet.address)} scored {scored.score}"
    body = (
        f"Wallet {wallet.address} on {wallet.chain} scored {scored.score} "
        f"({scored.risk_level}). {narrative_summary} "
        f"Recommended action: {recommended_action}."
    )
    return title, body, risk_to_severity(scored.risk_level)


def _watchlist_hit_text(
    wallet: WalletInput,
    scored: WalletScore,
    narrative_summary: str,
) -> tuple[str, str, AlertSeverity]:
    title = f"Watchlist hit: {_short(wallet.address)} — score {scored.score}"
    body = (
        f"Monitored wallet {wallet.address} on {wallet.chain} was re-analysed. "
        f"Current score: {scored.score} ({scored.risk_level}). {narrative_summary}"
    )
    return title, body, risk_to_severity(scored.risk_level)


def _risk_change_text(
    wallet: WalletInput,
    scored: WalletScore,
    prev_score: int,
) -> tuple[str, str, AlertSeverity]:
    delta = scored.score - prev_score
    direction = "increased" if delta > 0 else "decreased"
    title = (
        f"Risk score {direction}: {_short(wallet.address)} "
        f"{prev_score} → {scored.score}"
    )
    body = (
        f"Wallet {wallet.address} on {wallet.chain} risk score {direction} "
        f"by {abs(delta)} points (from {prev_score} to {scored.score}, "
        f"now {scored.risk_level})."
    )
    # De-escalations are informational; escalations inherit current risk level.
    sev: AlertSeverity = "info" if delta < 0 else risk_to_severity(scored.risk_level)
    return title, body, sev


def _volume_spike_text(
    wallet: WalletInput,
    scored: WalletScore,
) -> tuple[str, str, AlertSeverity]:
    title = (
        f"Volume spike: {_short(wallet.address)} "
        f"${wallet.volume_24h_usd:,.0f} / {wallet.txn_24h} txns"
    )
    body = (
        f"Wallet {wallet.address} on {wallet.chain} recorded "
        f"${wallet.volume_24h_usd:,.0f} volume and {wallet.txn_24h} transactions "
        f"in the last 24 h. Current risk score: {scored.score} ({scored.risk_level})."
    )
    sev = risk_to_severity(scored.risk_level)
    # Ensure volume spikes are at least "warning" even for low-risk wallets.
    return title, body, ("warning" if sev == "info" else sev)


# ── Candidate ─────────────────────────────────────────────────────────────────
class AlertCandidate:
    """
    Represents one alert that should be saved to the DB and potentially
    fire a webhook. Created by evaluate_wallet_alerts(); callers decide
    whether and how to persist.
    """

    __slots__ = ("alert_type", "trigger", "severity", "title", "body", "prev_score")

    def __init__(
        self,
        alert_type: AlertType,
        trigger: AlertTrigger,
        severity: AlertSeverity,
        title: str,
        body: str,
        prev_score: Optional[int] = None,
    ) -> None:
        self.alert_type: AlertType = alert_type
        self.trigger: AlertTrigger = trigger
        self.severity: AlertSeverity = severity
        self.title: str = title
        self.body: str = body
        self.prev_score: Optional[int] = prev_score

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"AlertCandidate(type={self.alert_type!r}, severity={self.severity!r}, "
            f"title={self.title!r})"
        )


# ── Public evaluation API ─────────────────────────────────────────────────────
def evaluate_wallet_alerts(
    wallet: WalletInput,
    scored: WalletScore,
    *,
    is_watchlist: bool = False,
    prev_score: Optional[int] = None,
    narrative_summary: str = "",
    recommended_action: str = "monitor",
) -> list[AlertCandidate]:
    """
    Evaluate a wallet analysis result and return a list of AlertCandidates.

    Parameters
    ----------
    wallet:               Input wallet data used for the analysis.
    scored:               Risk-scoring result (score + risk_level).
    is_watchlist:         True if the wallet is on the tenant's watchlist.
    prev_score:           Previous score for this wallet (enables risk_change alerts).
    narrative_summary:    Human-readable narrative text from the intelligence layer.
    recommended_action:   Recommended compliance action from the intelligence layer.

    Returns
    -------
    List of AlertCandidate objects (may be empty). Callers should persist each
    candidate via db.save_alert_event().
    """
    candidates: list[AlertCandidate] = []
    fired: set[AlertType] = set()

    # ── 1. Watchlist hit ────────────────────────────────────────────────────
    if is_watchlist and scored.score >= SCORE_THRESHOLD_WATCHLIST:
        t, b, sev = _watchlist_hit_text(wallet, scored, narrative_summary)
        candidates.append(
            AlertCandidate("watchlist_hit", "watchlist_activity", sev, t, b)
        )
        fired.add("watchlist_hit")

    # ── 2. Score threshold ──────────────────────────────────────────────────
    # Fire for non-watchlist wallets above CRITICAL threshold, or for watched
    # wallets above HIGH threshold (in addition to watchlist_hit).
    fire_threshold = (
        (not is_watchlist and scored.score >= SCORE_THRESHOLD_CRITICAL)
        or (is_watchlist and scored.score >= SCORE_THRESHOLD_HIGH)
    )
    if fire_threshold:
        t, b, sev = _score_threshold_text(
            wallet, scored, narrative_summary, recommended_action
        )
        candidates.append(
            AlertCandidate("score_threshold", "score_threshold", sev, t, b)
        )
        fired.add("score_threshold")

    # ── 3. Risk change ──────────────────────────────────────────────────────
    if prev_score is not None and abs(scored.score - prev_score) >= RISK_CHANGE_MIN_DELTA:
        t, b, sev = _risk_change_text(wallet, scored, prev_score)
        candidates.append(
            AlertCandidate(
                "risk_change", "score_threshold", sev, t, b, prev_score=prev_score
            )
        )
        fired.add("risk_change")

    # ── 4. Volume spike ─────────────────────────────────────────────────────
    # Only fires when no higher-priority alert (score_threshold / watchlist_hit)
    # already fired, to reduce alert fatigue for high-risk wallets.
    is_spike = (
        wallet.volume_24h_usd >= VOLUME_SPIKE_USD
        or wallet.txn_24h >= TXN_SPIKE_COUNT
    )
    if is_spike and not (fired & {"score_threshold", "watchlist_hit"}):
        t, b, sev = _volume_spike_text(wallet, scored)
        candidates.append(
            AlertCandidate("volume_spike", "score_threshold", sev, t, b)
        )

    return candidates
