from fastapi.testclient import TestClient

from app.cluster import build_cluster
from app.live_cluster import build_live_cluster
from app.main import app
from app.schemas import WalletInput


def _wallet(**overrides) -> WalletInput:
    payload = {
        "chain": "bsc",
        "address": "0xAABBCCDD11223344",
        "txn_24h": 320,
        "volume_24h_usd": 980_000,
        "sanctions_exposure_pct": 18,
        "mixer_exposure_pct": 14,
        "bridge_hops": 4,
    }
    payload.update(overrides)
    return WalletInput(**payload)


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_build_cluster_returns_heuristics_confidence_and_cross_chain_graph():
    wallet = _wallet()
    cluster = build_cluster(wallet, root_score_int=82)

    assert cluster.cluster_id
    assert cluster.root_address == wallet.address
    assert cluster.confidence >= 60
    assert cluster.cluster_score >= 82
    assert len(cluster.nodes) >= 3
    assert len(cluster.edges) >= 2
    assert cluster.heuristics
    assert any(edge.evidence for edge in cluster.edges)
    assert any(edge.relation in {"shared_funding_source", "common_counterparty", "synchronized_activity", "cross_chain_bridge"} for edge in cluster.edges)
    assert any(node.is_root for node in cluster.nodes)
    assert all(0 <= node.confidence <= 100 for node in cluster.nodes)
    assert any(h.heuristic == "shared_funding_source" for h in cluster.heuristics)



def test_cluster_endpoint_accepts_activity_context(tmp_path, monkeypatch):
    db_path = str(tmp_path / "cluster_endpoint.db")
    monkeypatch.setenv("COMPLIANCE_DB_PATH", db_path)
    monkeypatch.setenv("COMPLIANCE_ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("COMPLIANCE_ADMIN_PASSWORD", "OwnerPass123!")
    monkeypatch.setenv("COMPLIANCE_ADMIN_TENANT", "tenant-a")
    monkeypatch.setenv("COMPLIANCE_ADMIN_ROLE", "admin")

    with TestClient(app) as client:
        token = _login(client, "owner@test.local", "OwnerPass123!")
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get(
            "/wallets/0xAABBCCDD11223344/cluster"
            "?chain=bsc"
            "&txn_24h=320"
            "&volume_24h_usd=980000"
            "&sanctions_exposure_pct=18"
            "&mixer_exposure_pct=14"
            "&bridge_hops=4",
            headers=headers,
        )
        assert response.status_code == 200
        payload = response.json()

        assert payload["root_address"] == "0xAABBCCDD11223344"
        assert payload["cluster_id"]
        assert payload["confidence"] >= 60
        assert payload["cluster_score"] >= 1
        assert payload["cross_chain"] is True
        assert payload["heuristics"]
        assert payload["refresh_suggested_after_sec"] <= 45
        assert any(edge["relation"] == "cross_chain_bridge" for edge in payload["edges"])
        assert any(edge["evidence"] for edge in payload["edges"])
        assert any(node["activity_band"] in {"moderate", "high"} for node in payload["nodes"])


def test_build_live_cluster_uses_recent_counterparties(monkeypatch):
    wallet = WalletInput(
        chain="ethereum",
        address="0x1111111111111111111111111111111111111111",
        txn_24h=18,
        volume_24h_usd=250000,
        sanctions_exposure_pct=0,
        mixer_exposure_pct=0,
        bridge_hops=0,
    )

    def fake_fetch_json(url: str):
        if url.endswith(f"/addresses/{wallet.address}"):
            return {"coin_balance": "0", "exchange_rate": "2000"}
        if url.endswith(f"/addresses/{wallet.address}/transactions"):
            return {
                "items": [
                    {
                        "timestamp": "2026-03-26T20:00:00.000000Z",
                        "from": {"hash": wallet.address},
                        "to": {"hash": "0x2222222222222222222222222222222222222222"},
                        "value": "1000000000000000000",
                    },
                    {
                        "timestamp": "2026-03-26T19:50:00.000000Z",
                        "from": {"hash": "0x3333333333333333333333333333333333333333"},
                        "to": {"hash": wallet.address},
                        "value": "500000000000000000",
                    },
                    {
                        "timestamp": "2026-03-26T19:40:00.000000Z",
                        "from": {"hash": wallet.address},
                        "to": {"hash": "0x2222222222222222222222222222222222222222"},
                        "value": "250000000000000000",
                    },
                ],
                "next_page_params": None,
            }
        raise AssertionError(url)

    monkeypatch.setattr("app.live_cluster._fetch_json", fake_fetch_json)

    cluster = build_live_cluster(wallet, root_score_int=12)

    assert cluster is not None
    assert cluster.root_address == wallet.address
    assert len(cluster.nodes) == 3
    assert any(edge.relation in {"shared_funding_source", "synchronized_activity", "co_funded", "common_counterparty"} for edge in cluster.edges)
    assert cluster.narrative.startswith("Live Ethereum cluster built")
    assert cluster.cross_chain is False


def test_build_live_cluster_returns_root_only_when_no_recent_counterparties(monkeypatch):
    wallet = WalletInput(
        chain="ethereum",
        address="0x1111111111111111111111111111111111111111",
        txn_24h=0,
        volume_24h_usd=0,
        sanctions_exposure_pct=0,
        mixer_exposure_pct=0,
        bridge_hops=0,
    )

    def fake_fetch_json(url: str):
        if url.endswith(f"/addresses/{wallet.address}"):
            return {"coin_balance": "0", "exchange_rate": "2000"}
        if url.endswith(f"/addresses/{wallet.address}/transactions"):
            return {"items": [], "next_page_params": None}
        raise AssertionError(url)

    monkeypatch.setattr("app.live_cluster._fetch_json", fake_fetch_json)

    cluster = build_live_cluster(wallet, root_score_int=0)

    assert cluster is not None
    assert len(cluster.nodes) == 1
    assert cluster.edges == []
    assert cluster.narrative.startswith("Live Ethereum cluster found no recent counterparties")


def test_build_live_cluster_returns_root_only_when_explorer_rejects_first_page(monkeypatch):
    from email.message import Message
    from urllib.error import HTTPError

    wallet = WalletInput(
        chain="ethereum",
        address="0x1111111111111111111111111111111111111111",
        txn_24h=0,
        volume_24h_usd=0,
        sanctions_exposure_pct=0,
        mixer_exposure_pct=0,
        bridge_hops=0,
    )

    def fake_fetch_json(url: str):
        if url.endswith(f"/addresses/{wallet.address}"):
            return {"coin_balance": "0", "exchange_rate": "2000"}
        if url.endswith(f"/addresses/{wallet.address}/transactions"):
            raise HTTPError(url, 422, "unprocessable", Message(), None)
        raise AssertionError(url)

    monkeypatch.setattr("app.live_cluster._fetch_json", fake_fetch_json)

    cluster = build_live_cluster(wallet, root_score_int=0)

    assert cluster is not None
    assert len(cluster.nodes) == 1
    assert cluster.edges == []
    assert cluster.narrative.startswith("Live Ethereum cluster found no recent counterparties")
