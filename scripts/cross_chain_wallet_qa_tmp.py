from __future__ import annotations

import json
import urllib.parse
import urllib.request
from urllib.error import HTTPError

BASE = "http://127.0.0.1:8000"
LOGIN = {"email": "founder@demo.local", "password": "ChangeMe123!"}

WALLETS = [
    {
        "chain": "ethereum",
        "label": "Vitalik EOA",
        "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "mode": "live",
    },
    {
        "chain": "base",
        "label": "Base WETH contract",
        "address": "0x4200000000000000000000000000000000000006",
        "mode": "manual",
        "payload": {"txn_24h": 84, "volume_24h_usd": 250000, "sanctions_exposure_pct": 2, "mixer_exposure_pct": 0, "bridge_hops": 1},
    },
    {
        "chain": "arbitrum",
        "label": "Arbitrum WETH contract",
        "address": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "mode": "manual",
        "payload": {"txn_24h": 61, "volume_24h_usd": 180000, "sanctions_exposure_pct": 3, "mixer_exposure_pct": 1, "bridge_hops": 2},
    },
    {
        "chain": "bsc",
        "label": "Binance hot wallet BSC",
        "address": "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3",
        "mode": "manual",
        "payload": {"txn_24h": 142, "volume_24h_usd": 540000, "sanctions_exposure_pct": 5, "mixer_exposure_pct": 2, "bridge_hops": 1},
    },
    {
        "chain": "polygon",
        "label": "Polygon WETH contract",
        "address": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "mode": "manual",
        "payload": {"txn_24h": 73, "volume_24h_usd": 210000, "sanctions_exposure_pct": 4, "mixer_exposure_pct": 1, "bridge_hops": 2},
    },
    {
        "chain": "solana",
        "label": "Solana vote program address",
        "address": "Vote111111111111111111111111111111111111111",
        "mode": "manual",
        "payload": {"txn_24h": 39, "volume_24h_usd": 95000, "sanctions_exposure_pct": 1, "mixer_exposure_pct": 0, "bridge_hops": 0},
    },
]


def req(method: str, path: str, payload: dict | None = None, token: str | None = None):
    headers: dict[str, str] = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {raw}") from exc


def main() -> None:
    token = req("POST", "/auth/login", LOGIN)["access_token"]
    results = []

    for wallet in WALLETS:
        address = wallet["address"]
        encoded = urllib.parse.quote(address, safe="")
        result = {
            "chain": wallet["chain"],
            "label": wallet["label"],
            "address": address,
            "mode": wallet["mode"],
        }
        try:
            if wallet["mode"] == "live":
                enrich = req("GET", f"/wallets/{encoded}/enrich?chain={wallet['chain']}", token=token)
                intelligence = req("POST", "/wallets/intelligence", enrich, token=token)
                cluster = req("GET", f"/wallets/{encoded}/cluster?chain={wallet['chain']}", token=token)
                result["enrich"] = {
                    "live_supported": enrich["live_supported"],
                    "txn_24h": enrich["txn_24h"],
                    "volume_24h_usd": round(enrich["volume_24h_usd"], 2),
                }
            else:
                payload = {"address": address, "chain": wallet["chain"], **wallet["payload"]}
                intelligence = req("POST", "/wallets/intelligence", payload, token=token)
                query = urllib.parse.urlencode({"chain": wallet["chain"], **wallet["payload"]})
                cluster = req("GET", f"/wallets/{encoded}/cluster?{query}", token=token)
                result["manual_input"] = wallet["payload"]

            result["intelligence"] = {
                "score": intelligence["score"],
                "risk_level": intelligence["risk_level"],
                "fingerprints": len(intelligence["fingerprints"]),
                "recommended_action": intelligence["narrative"]["recommended_action"],
            }
            result["cluster"] = {
                "node_count": len(cluster["nodes"]),
                "edge_count": len(cluster["edges"]),
                "cross_chain": cluster["cross_chain"],
                "cluster_risk": cluster["cluster_risk"],
                "narrative": cluster["narrative"][:160],
            }
            result["passed"] = True
        except Exception as exc:
            result["passed"] = False
            result["error"] = str(exc)
        results.append(result)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
