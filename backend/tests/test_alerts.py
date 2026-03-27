"""
tests/test_alerts.py
--------------------
Integration tests for the full alert system:
  - alert_engine: candidate generation (unit tests)
  - db: persistence, filtering, ack-all, resolve, cursor feed
  - incidents: create, link/unlink, update status, cross-tenant isolation
"""

import pytest
from datetime import datetime, timezone

from app.db import (
    acknowledge_alert,
    acknowledge_all_alerts,
    create_alert_manual,
    create_incident,
    get_alert_feed,
    get_incident_detail,
    init_db,
    link_alert_to_incident,
    list_alerts,
    list_incidents,
    resolve_alert,
    save_alert_event,
    unlink_alert_from_incident,
    update_incident,
)
from app.alert_engine import (
    RISK_CHANGE_MIN_DELTA,
    SCORE_THRESHOLD_CRITICAL,
    SCORE_THRESHOLD_WATCHLIST,
    evaluate_wallet_alerts,
)
from app.schemas import AlertSeverity, WalletInput, WalletScore


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wallet(address: str = "0xTEST00", score: int = 50) -> tuple[WalletInput, WalletScore]:
    w = WalletInput(
        chain="ethereum",
        address=address,
        txn_24h=10,
        volume_24h_usd=1_000,
        sanctions_exposure_pct=0,
        mixer_exposure_pct=0,
        bridge_hops=0,
    )
    risk = "low" if score < 40 else ("medium" if score < 65 else ("high" if score < 85 else "critical"))
    s = WalletScore(address=address, score=score, risk_level=risk, reason="test")  # type: ignore[arg-type]
    return w, s


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_alerts.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_file)
    init_db(db_file)
    return db_file


# ══════════════════════════════════════════════════════════════════════════════
# Alert engine – unit tests (no DB)
# ══════════════════════════════════════════════════════════════════════════════

class TestAlertEngine:
    def test_no_candidates_for_low_risk(self):
        w, s = _wallet(score=20)
        assert evaluate_wallet_alerts(w, s) == []

    def test_score_threshold_fires_at_critical(self):
        w, s = _wallet(score=SCORE_THRESHOLD_CRITICAL)
        candidates = evaluate_wallet_alerts(w, s, narrative_summary="flagged", recommended_action="block")
        types = [c.alert_type for c in candidates]
        assert "score_threshold" in types
        thresh = next(c for c in candidates if c.alert_type == "score_threshold")
        assert thresh.severity == "critical"
        assert thresh.trigger == "score_threshold"

    def test_score_below_critical_no_threshold_alert(self):
        w, s = _wallet(score=SCORE_THRESHOLD_CRITICAL - 1)
        candidates = evaluate_wallet_alerts(w, s)
        assert not any(c.alert_type == "score_threshold" for c in candidates)

    def test_watchlist_hit_fires_at_watchlist_threshold(self):
        w, s = _wallet(score=SCORE_THRESHOLD_WATCHLIST)
        candidates = evaluate_wallet_alerts(w, s, is_watchlist=True)
        assert any(c.alert_type == "watchlist_hit" for c in candidates)
        hit = next(c for c in candidates if c.alert_type == "watchlist_hit")
        assert hit.trigger == "watchlist_activity"

    def test_watched_high_score_fires_both_watchlist_and_threshold(self):
        w, s = _wallet(score=70)  # above SCORE_THRESHOLD_HIGH (65)
        candidates = evaluate_wallet_alerts(w, s, is_watchlist=True)
        types = [c.alert_type for c in candidates]
        assert "watchlist_hit" in types
        assert "score_threshold" in types

    def test_risk_change_alert_upward(self):
        w, s = _wallet(score=50)
        prev = 50 - RISK_CHANGE_MIN_DELTA  # exactly at threshold
        candidates = evaluate_wallet_alerts(w, s, prev_score=prev)
        assert any(c.alert_type == "risk_change" for c in candidates)
        change = next(c for c in candidates if c.alert_type == "risk_change")
        assert change.prev_score == prev
        assert change.severity != "info"  # upward escalation

    def test_risk_change_alert_downward_is_info(self):
        w, s = _wallet(score=20)
        prev = 20 + RISK_CHANGE_MIN_DELTA  # score decreased
        candidates = evaluate_wallet_alerts(w, s, prev_score=prev)
        change = next((c for c in candidates if c.alert_type == "risk_change"), None)
        assert change is not None
        assert change.severity == "info"

    def test_risk_change_below_delta_no_alert(self):
        w, s = _wallet(score=25)
        candidates = evaluate_wallet_alerts(w, s, prev_score=25 - (RISK_CHANGE_MIN_DELTA - 1))
        assert not any(c.alert_type == "risk_change" for c in candidates)

    def test_volume_spike_fires_when_no_other_alert(self):
        w = WalletInput(
            chain="ethereum", address="0xSPIKE1", txn_24h=10,
            volume_24h_usd=600_000, sanctions_exposure_pct=0,
            mixer_exposure_pct=0, bridge_hops=0,
        )
        s = WalletScore(address="0xSPIKE", score=15, risk_level="low", reason="volume")
        candidates = evaluate_wallet_alerts(w, s)
        assert any(c.alert_type == "volume_spike" for c in candidates)
        spike = next(c for c in candidates if c.alert_type == "volume_spike")
        assert spike.severity in ("warning", "high", "critical")  # never "info"

    def test_volume_spike_suppressed_by_score_threshold(self):
        w = WalletInput(
            chain="bsc", address="0xBIG0001", txn_24h=600,
            volume_24h_usd=800_000, sanctions_exposure_pct=40,
            mixer_exposure_pct=0, bridge_hops=0,
        )
        s = WalletScore(address="0xBIG", score=90, risk_level="critical", reason="risky")
        candidates = evaluate_wallet_alerts(w, s)
        types = [c.alert_type for c in candidates]
        assert "score_threshold" in types
        assert "volume_spike" not in types  # suppressed

    def test_txn_spike_fires_volume_spike(self):
        w = WalletInput(
            chain="ethereum", address="0xTXN0001", txn_24h=600,  # above TXN_SPIKE_COUNT
            volume_24h_usd=1_000, sanctions_exposure_pct=0,
            mixer_exposure_pct=0, bridge_hops=0,
        )
        s = WalletScore(address="0xTXN", score=10, risk_level="low", reason="txns")
        candidates = evaluate_wallet_alerts(w, s)
        assert any(c.alert_type == "volume_spike" for c in candidates)


# ══════════════════════════════════════════════════════════════════════════════
# DB persistence
# ══════════════════════════════════════════════════════════════════════════════

class TestAlertPersistence:
    def test_save_and_list_alert_with_new_fields(self, db):
        a = save_alert_event(
            tenant_id="t1", trigger="score_threshold", chain="ethereum",
            address="0xABC", score=88, risk_level="critical",
            title="Test", body="Body",
            created_at=_now(),
            alert_type="score_threshold", severity="critical",
            db_path=db,
        )
        assert a.id > 0
        assert a.severity == "critical"
        assert a.alert_type == "score_threshold"
        assert a.acknowledged is False

        items = list_alerts(tenant_id="t1", db_path=db)
        assert len(items) == 1
        assert items[0].severity == "critical"

    def test_list_alerts_filter_severity(self, db):
        save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                         address="0x1", score=88, risk_level="critical", title="A", body="B",
                         created_at=_now(), severity="critical", db_path=db)
        save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                         address="0x2", score=45, risk_level="medium", title="C", body="D",
                         created_at=_now(), severity="warning", db_path=db)

        critical_only = list_alerts(tenant_id="t1", severity="critical", db_path=db)
        assert len(critical_only) == 1
        assert critical_only[0].severity == "critical"

    def test_list_alerts_filter_alert_type(self, db):
        save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                         address="0x1", score=88, risk_level="critical", title="A", body="B",
                         created_at=_now(), alert_type="score_threshold", db_path=db)
        save_alert_event(tenant_id="t1", trigger="watchlist_activity", chain="ethereum",
                         address="0x2", score=55, risk_level="medium", title="W", body="B",
                         created_at=_now(), alert_type="watchlist_hit", db_path=db)

        wl_only = list_alerts(tenant_id="t1", alert_type="watchlist_hit", db_path=db)
        assert len(wl_only) == 1
        assert wl_only[0].alert_type == "watchlist_hit"

    def test_acknowledge_sets_acknowledged_at(self, db):
        a = save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                             address="0xACK", score=70, risk_level="high", title="T", body="B",
                             created_at=_now(), db_path=db)
        ts = _now()
        ok = acknowledge_alert(a.id, "t1", ts, db_path=db)
        assert ok
        items = list_alerts(tenant_id="t1", db_path=db)
        assert items[0].acknowledged is True
        assert items[0].acknowledged_at == ts

    def test_acknowledge_all_acks_all_unread(self, db):
        for i in range(3):
            save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                             address=f"0x{i}", score=50, risk_level="medium",
                             title=f"Alert {i}", body="body", created_at=_now(), db_path=db)
        count = acknowledge_all_alerts("t1", _now(), db_path=db)
        assert count == 3
        unread = list_alerts(tenant_id="t1", unacked_only=True, db_path=db)
        assert len(unread) == 0

    def test_acknowledge_all_only_affects_unread(self, db):
        a1 = save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                              address="0x1", score=50, risk_level="medium",
                              title="A1", body="body", created_at=_now(), db_path=db)
        acknowledge_alert(a1.id, "t1", _now(), db_path=db)  # pre-ack
        save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                         address="0x2", score=50, risk_level="medium",
                         title="A2", body="body", created_at=_now(), db_path=db)
        count = acknowledge_all_alerts("t1", _now(), db_path=db)
        assert count == 1  # only the unread one

    def test_resolve_alert(self, db):
        a = save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                             address="0xRES", score=70, risk_level="high",
                             title="Resolve me", body="body", created_at=_now(), db_path=db)
        ok = resolve_alert(a.id, "t1", _now(), db_path=db)
        assert ok
        items = list_alerts(tenant_id="t1", db_path=db)
        assert items[0].resolved_at is not None
        assert items[0].acknowledged is True

    def test_create_alert_manual(self, db):
        a = create_alert_manual(
            tenant_id="t1", alert_type="manual", severity="high",
            chain="bsc", address="0xMAN", score=60, risk_level="medium",
            title="Manual alert", body="Manually created",
            created_at=_now(), db_path=db,
        )
        assert a.alert_type == "manual"
        assert a.trigger == "manual"
        assert a.severity == "high"

    def test_alert_feed_cursor_ordering(self, db):
        a1 = save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                              address="0x1", score=50, risk_level="medium",
                              title="First", body="B", created_at=_now(), db_path=db)
        a2 = save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                              address="0x2", score=60, risk_level="medium",
                              title="Second", body="B", created_at=_now(), db_path=db)
        a3 = save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                              address="0x3", score=70, risk_level="high",
                              title="Third", body="B", created_at=_now(), db_path=db)

        # Full feed — ascending order
        full = get_alert_feed("t1", since_id=0, db_path=db)
        assert len(full) == 3
        assert full[0].id < full[1].id < full[2].id  # ASC

        # Cursor fetch — only after a1
        after_first = get_alert_feed("t1", since_id=a1.id, db_path=db)
        assert len(after_first) == 2
        assert {r.id for r in after_first} == {a2.id, a3.id}

    def test_prev_score_persisted(self, db):
        a = save_alert_event(
            tenant_id="t1", trigger="score_threshold", chain="ethereum",
            address="0xDELTA", score=65, risk_level="high",
            title="Risk jump", body="B",
            created_at=_now(), alert_type="risk_change", prev_score=40,
            db_path=db,
        )
        items = list_alerts(tenant_id="t1", db_path=db)
        assert items[0].prev_score == 40

    def test_cross_tenant_isolation(self, db):
        save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                         address="0x1", score=88, risk_level="critical",
                         title="T1", body="B", created_at=_now(), db_path=db)
        items_t2 = list_alerts(tenant_id="t2", db_path=db)
        assert items_t2 == []


# ══════════════════════════════════════════════════════════════════════════════
# Incidents
# ══════════════════════════════════════════════════════════════════════════════

class TestIncidents:
    def test_create_incident_empty(self, db):
        inc = create_incident(
            tenant_id="t1", title="Suspicious cluster", description="Multi-wallet scheme",
            severity="high", created_by="analyst@demo.local", created_at=_now(),
            db_path=db,
        )
        assert inc.id > 0
        assert inc.status == "open"
        assert inc.alert_count == 0
        assert inc.created_by == "analyst@demo.local"

    def test_create_incident_with_initial_alerts(self, db):
        a1 = save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                              address="0xA", score=90, risk_level="critical",
                              title="A1", body="B", created_at=_now(), db_path=db)
        a2 = save_alert_event(tenant_id="t1", trigger="watchlist_activity", chain="bsc",
                              address="0xB", score=75, risk_level="high",
                              title="A2", body="B", created_at=_now(), db_path=db)

        inc = create_incident(
            tenant_id="t1", title="Cluster incident", description="",
            severity="critical", created_by="admin@demo.local", created_at=_now(),
            alert_ids=[a1.id, a2.id], db_path=db,
        )
        assert inc.alert_count == 2

        detail = get_incident_detail(inc.id, "t1", db_path=db)
        assert detail is not None
        assert len(detail.alerts) == 2
        linked_ids = {a.id for a in detail.alerts}
        assert a1.id in linked_ids
        assert a2.id in linked_ids

    def test_link_unlink_alert(self, db):
        inc = create_incident(tenant_id="t1", title="Inc", description="",
                              severity="warning", created_by="a@b.c", created_at=_now(),
                              db_path=db)
        a = save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                             address="0xLINK", score=70, risk_level="high",
                             title="Link me", body="B", created_at=_now(), db_path=db)

        ok = link_alert_to_incident(a.id, inc.id, "t1", _now(), db_path=db)
        assert ok

        detail = get_incident_detail(inc.id, "t1", db_path=db)
        assert detail is not None
        assert detail.alert_count == 1
        assert len(detail.alerts) == 1

        ok2 = unlink_alert_from_incident(a.id, inc.id, "t1", _now(), db_path=db)
        assert ok2

        detail2 = get_incident_detail(inc.id, "t1", db_path=db)
        assert detail2 is not None
        assert detail2.alert_count == 0
        assert len(detail2.alerts) == 0

    def test_link_alert_to_different_incident(self, db):
        """Moving an alert from one incident to another adjusts both counts."""
        inc1 = create_incident(tenant_id="t1", title="Inc1", description="",
                               severity="high", created_by="a@b.c", created_at=_now(), db_path=db)
        inc2 = create_incident(tenant_id="t1", title="Inc2", description="",
                               severity="warning", created_by="a@b.c", created_at=_now(), db_path=db)
        a = save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                             address="0xMOVE", score=70, risk_level="high",
                             title="Move me", body="B", created_at=_now(), db_path=db)

        link_alert_to_incident(a.id, inc1.id, "t1", _now(), db_path=db)
        d1 = get_incident_detail(inc1.id, "t1", db_path=db)
        assert d1 is not None and d1.alert_count == 1

        # Move to inc2
        link_alert_to_incident(a.id, inc2.id, "t1", _now(), db_path=db)
        d1_after = get_incident_detail(inc1.id, "t1", db_path=db)
        d2_after = get_incident_detail(inc2.id, "t1", db_path=db)
        assert d1_after is not None and d1_after.alert_count == 0
        assert d2_after is not None and d2_after.alert_count == 1

    def test_update_incident_status_lifecycle(self, db):
        inc = create_incident(tenant_id="t1", title="Inc", description="",
                              severity="high", created_by="a@b.c", created_at=_now(), db_path=db)

        investigating = update_incident(inc.id, "t1", _now(), status="investigating", db_path=db)
        assert investigating is not None
        assert investigating.status == "investigating"
        assert investigating.resolved_at is None

        resolved = update_incident(inc.id, "t1", _now(), status="resolved", db_path=db)
        assert resolved is not None
        assert resolved.status == "resolved"
        assert resolved.resolved_at is not None

        # Re-opening should clear resolved_at
        reopened = update_incident(inc.id, "t1", _now(), status="open", db_path=db)
        assert reopened is not None
        assert reopened.status == "open"
        assert reopened.resolved_at is None

    def test_update_incident_not_found(self, db):
        result = update_incident(9999, "t1", _now(), status="closed", db_path=db)
        assert result is None

    def test_list_incidents_filter_by_status(self, db):
        cases: list[tuple[str, AlertSeverity]] = [("A", "high"), ("B", "warning"), ("C", "critical")]
        for title, sev in cases:
            create_incident(tenant_id="t1", title=title, description="",
                            severity=sev, created_by="a@b.c", created_at=_now(), db_path=db)

        all_items = list_incidents("t1", db_path=db)
        assert len(all_items) == 3

        # Resolve one
        update_incident(all_items[0].id, "t1", _now(), status="resolved", db_path=db)
        resolved_items = list_incidents("t1", status="resolved", db_path=db)
        open_items = list_incidents("t1", status="open", db_path=db)
        assert len(resolved_items) == 1
        assert len(open_items) == 2

    def test_cross_tenant_isolation(self, db):
        inc = create_incident(tenant_id="t1", title="T1 incident", description="",
                              severity="high", created_by="a@b.c", created_at=_now(), db_path=db)
        assert get_incident_detail(inc.id, "t2", db_path=db) is None
        assert list_incidents("t2", db_path=db) == []

    def test_unlink_wrong_incident_returns_false(self, db):
        inc = create_incident(tenant_id="t1", title="Inc", description="",
                              severity="warning", created_by="a@b.c", created_at=_now(), db_path=db)
        a = save_alert_event(tenant_id="t1", trigger="score_threshold", chain="ethereum",
                             address="0xW", score=50, risk_level="medium",
                             title="W", body="B", created_at=_now(), db_path=db)
        # Alert not linked to any incident — unlink should return False
        ok = unlink_alert_from_incident(a.id, inc.id, "t1", _now(), db_path=db)
        assert ok is False
