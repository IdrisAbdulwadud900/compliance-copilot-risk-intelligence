from fastapi.testclient import TestClient

from app.db import init_db, save_analysis
from app.main import app
from app.schemas import WalletInput, WalletScore


def test_dashboard_returns_empty_alerts_for_empty_workspace(tmp_path, monkeypatch):
    db_path = str(tmp_path / "dashboard_empty.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_API_KEYS", "test-key:tenant-a:admin")

    init_db(db_path)

    with TestClient(app) as client:
        response = client.get("/dashboard", headers={"x-api-key": "test-key"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_wallets_monitored"] == 0
    assert payload["alerts_today"] == 0
    assert payload["critical_alerts_today"] == 0
    assert payload["alerts"] == []


def test_dashboard_returns_real_alerts_from_saved_analyses(tmp_path, monkeypatch):
    db_path = str(tmp_path / "dashboard_real.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_API_KEYS", "test-key:tenant-a:admin")

    init_db(db_path)
    wallet = WalletInput(
        chain="ethereum",
        address="0xABCDEF1122334455",
        txn_24h=88,
        volume_24h_usd=120000,
        sanctions_exposure_pct=3,
        mixer_exposure_pct=8,
        bridge_hops=2,
    )
    scored = WalletScore(
        address=wallet.address,
        score=78,
        risk_level="high",
        reason="elevated signal",
    )
    save_analysis(
        "tenant-a",
        wallet,
        scored,
        "High risk explanation",
        "2026-03-27T00:00:00Z",
        db_path,
    )

    with TestClient(app) as client:
        response = client.get("/dashboard", headers={"x-api-key": "test-key"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_wallets_monitored"] == 1
    assert payload["alerts_today"] == 1
    assert payload["critical_alerts_today"] == 0
    assert len(payload["alerts"]) == 1
    assert payload["alerts"][0]["wallet"] == wallet.address
    assert payload["alerts"][0]["score"] == scored.score