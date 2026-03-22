from app.db import init_db, list_recent_analyses, save_analysis
from app.schemas import WalletInput, WalletScore


def test_save_and_list_analysis(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    wallet = WalletInput(
        address="0xABCDEF1122334455",
        txn_24h=88,
        volume_24h_usd=120000,
        sanctions_exposure_pct=3,
        mixer_exposure_pct=8,
        bridge_hops=2,
    )
    scored = WalletScore(
        address=wallet.address,
        score=38,
        risk_level="low",
        reason="limited high-risk signal",
    )

    saved = save_analysis(
        "tenant-a",
        wallet,
        scored,
        "Low risk explanation",
        "2026-03-21T00:00:00Z",
        db_path,
    )
    assert saved.id > 0

    items = list_recent_analyses(tenant_id="tenant-a", limit=5, db_path=db_path)
    assert len(items) == 1
    assert items[0].address == wallet.address
    assert items[0].score == scored.score

    other_items = list_recent_analyses(tenant_id="tenant-b", limit=5, db_path=db_path)
    assert other_items == []
