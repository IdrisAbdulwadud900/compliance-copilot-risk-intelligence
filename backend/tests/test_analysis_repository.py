from app.db import init_db
from app.repositories.analysis_repository import (
    list_recent_analyses,
    save_analysis,
    update_analysis_tags,
)
from app.schemas import WalletInput, WalletScore


def test_analysis_repository_save_list_and_tag_flow(tmp_path):
    db_path = str(tmp_path / "analysis_repo.db")
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
    assert saved.tags == []

    items = list_recent_analyses(tenant_id="tenant-a", limit=5, db_path=db_path)
    assert len(items) == 1
    assert items[0].address == wallet.address
    assert items[0].score == scored.score

    updated = update_analysis_tags(saved.id, "tenant-a", ["triage", "review"], db_path)
    assert updated is not None
    assert updated.tags == ["triage", "review"]

    missing = update_analysis_tags(9999, "tenant-a", ["missing"], db_path)
    assert missing is None
