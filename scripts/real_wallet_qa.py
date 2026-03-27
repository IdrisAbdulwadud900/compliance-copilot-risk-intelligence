from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


BASE_URL = "http://127.0.0.1:8000"
LOGIN_EMAIL = "founder@demo.local"
LOGIN_PASSWORD = "ChangeMe123!"


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


REAL_WALLETS = [
    {
        "label": "vitalik",
        "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        "expect_live_cluster": True,
    },
    {
        "label": "binance_hot",
        "address": "0x28C6c06298d514Db089934071355E5743bf21d60",
        "expect_live_cluster": True,
    },
    {
        "label": "usdc_contract",
        "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "expect_live_cluster": True,
    },
]


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token: Optional[str] = None

    def _request(self, method: str, path: str, payload: Optional[dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        body = None
        headers: Dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url=url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} -> {error.code}: {raw}") from error

    def login(self) -> None:
        payload = self._request(
            "POST",
            "/auth/login",
            {"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
        )
        self.token = payload["access_token"]

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", path, payload)

    def patch(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("PATCH", path, payload)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)


def log(message: str) -> None:
    print(message, flush=True)



def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)



def test_wallet_basics(client: ApiClient, wallet: dict[str, Any]) -> tuple[List[CheckResult], dict[str, Any], dict[str, Any], dict[str, Any]]:
    results: List[CheckResult] = []
    address = wallet["address"]
    encoded = urllib.parse.quote(address, safe="")
    log(f"[wallet:{wallet['label']}] enrich")

    enrich = client.get(f"/wallets/{encoded}/enrich?chain=ethereum")
    assert_true(enrich["address"].lower() == address.lower(), "enrichment returned wrong address")
    assert_true(enrich["chain"] == "ethereum", "enrichment returned wrong chain")
    assert_true(enrich["live_supported"] is True, "live enrichment should be supported")
    results.append(CheckResult(f"{wallet['label']} enrich", True, f"tx24h={enrich['txn_24h']} vol24h=${enrich['volume_24h_usd']:.2f}"))

    log(f"[wallet:{wallet['label']}] intelligence")
    intelligence = client.post("/wallets/intelligence", enrich)
    assert_true(intelligence["address"].lower() == address.lower(), "intelligence returned wrong address")
    assert_true(0 <= intelligence["score"] <= 100, "score out of range")
    if enrich["txn_24h"] > 0 or enrich["volume_24h_usd"] > 0:
        assert_true(len(intelligence["fingerprints"]) >= 1, "expected at least one fingerprint for an active wallet")
    else:
        assert_true(
            "no high-confidence behavioral patterns" in intelligence["narrative"]["summary"].lower(),
            "expected dormant low-signal wallets to return the neutral narrative",
        )
    results.append(CheckResult(f"{wallet['label']} intelligence", True, f"score={intelligence['score']} risk={intelligence['risk_level']}"))

    log(f"[wallet:{wallet['label']}] cluster")
    cluster = client.get(f"/wallets/{encoded}/cluster?chain=ethereum")
    assert_true(cluster["root_address"].lower() == address.lower(), "cluster returned wrong root")
    assert_true(len(cluster["nodes"]) >= 1, "cluster missing nodes")
    if wallet["expect_live_cluster"]:
        is_live_cluster = cluster["narrative"].startswith("Live Ethereum cluster built")
        is_live_root_only = cluster["narrative"].startswith("Live Ethereum cluster found no recent counterparties")
        assert_true(is_live_cluster or is_live_root_only, "expected live Ethereum cluster narrative")
        assert_true(cluster["cross_chain"] is False, "live ethereum cluster should not be cross-chain")
        if is_live_cluster:
            assert_true(len(cluster["edges"]) >= 1, "cluster missing edges")
        else:
            assert_true(len(cluster["nodes"]) == 1, "root-only live cluster should contain a single node")
            assert_true(len(cluster["edges"]) == 0, "root-only live cluster should not contain edges")
    results.append(CheckResult(f"{wallet['label']} cluster", True, f"nodes={len(cluster['nodes'])} edges={len(cluster['edges'])}"))

    return results, enrich, intelligence, cluster



def find_watchlist_entry(entries: list[dict[str, Any]], address: str) -> Optional[dict[str, Any]]:
    for entry in entries:
        if entry["address"].lower() == address.lower():
            return entry
    return None



def test_watchlist_alert_incident_case(client: ApiClient, enrich: dict[str, Any], intelligence: dict[str, Any], cluster: dict[str, Any]) -> List[CheckResult]:
    results: List[CheckResult] = []
    address = enrich["address"]
    label = "Real wallet QA"
    watch_entry: Optional[dict[str, Any]] = None

    log("[workflow] watchlist add/list")
    watchlist_before = client.get("/watchlist")["items"]
    existing = find_watchlist_entry(watchlist_before, address)
    if existing is None:
        watch_entry = client.post(
            "/watchlist",
            {
                "chain": "ethereum",
                "address": address,
                "label": label,
                "alert_on_activity": True,
            },
        )
    else:
        watch_entry = existing
    assert_true(watch_entry is not None, "watchlist entry was not available")
    if watch_entry is None:
        raise AssertionError("watchlist entry was not available")
    watch_entry_value = watch_entry
    results.append(CheckResult("watchlist add/list", True, f"entry_id={watch_entry_value['id']} label={watch_entry_value['label']}"))

    log("[workflow] watched intelligence + alerts")
    risky_real_wallet = dict(enrich)
    risky_real_wallet.update({
        "sanctions_exposure_pct": 25,
        "mixer_exposure_pct": 15,
        "bridge_hops": 4,
    })
    watched_analysis = client.post("/wallets/intelligence", risky_real_wallet)
    alerts = client.get("/alerts?limit=20&unacked_only=true")
    matching_alerts = [
        item for item in alerts["items"]
        if item["address"].lower() == address.lower() and item["alert_type"] in {"watchlist_hit", "score_threshold"}
    ]
    assert_true(len(matching_alerts) >= 1, "expected watchlist or score alert after watched analysis")
    target_alert = matching_alerts[0]
    results.append(CheckResult("watchlist-triggered alert", True, f"alert_id={target_alert['id']} type={target_alert['alert_type']} severity={target_alert['severity']}"))

    log("[workflow] alert ack/resolve")
    acked = client.post(f"/alerts/{target_alert['id']}/ack", {})
    assert_true(acked["acknowledged"] is True, "alert ack failed")
    resolved = client.patch(f"/alerts/{target_alert['id']}", {"resolved": True})
    assert_true(resolved["updated"] is True, "alert resolve failed")
    results.append(CheckResult("alert ack/resolve", True, f"alert_id={target_alert['id']}"))

    log("[workflow] incident create/update")
    incident = client.post(
        "/incidents",
        {
            "title": f"QA incident for {address[:10]}",
            "description": "Incident created during real-wallet QA validation.",
            "severity": target_alert["severity"],
            "alert_ids": [target_alert["id"]],
        },
    )
    assert_true(len(incident["alerts"]) >= 1, "incident should include linked alert")
    updated_incident = client.patch(f"/incidents/{incident['id']}", {"status": "investigating"})
    assert_true(updated_incident["status"] == "investigating", "incident status update failed")
    results.append(CheckResult("incident create/update", True, f"incident_id={incident['id']} alerts={len(incident['alerts'])}"))

    log("[workflow] case create/enrich/update")
    case = client.post(
        "/cases",
        {
            "title": f"QA case for {address[:10]}",
            "summary": "Case created during real-wallet QA validation.",
            "priority": "high",
            "primary_chain": "ethereum",
            "primary_address": address,
            "risk_score": watched_analysis["score"],
            "risk_level": watched_analysis["risk_level"],
            "source_type": "analysis",
            "source_ref": str(watched_analysis["analysis_id"]),
            "tags": ["qa", "real-wallet"],
        },
    )
    client.post(
        f"/cases/{case['id']}/notes",
        {
            "note_type": "observation",
            "body": "Observed real-wallet behavior and validated linked alert flow.",
            "tags": ["qa", "note"],
        },
    )
    client.post(
        f"/cases/{case['id']}/entities",
        {
            "entity_type": "cluster",
            "label": "Live Ethereum cluster",
            "chain": "ethereum",
            "reference": cluster["cluster_id"],
            "risk_score": cluster["cluster_score"],
            "risk_level": cluster["cluster_risk"],
        },
    )
    client.post(
        f"/cases/{case['id']}/attachments",
        {
            "file_name": "qa-notes.txt",
            "file_url": "https://example.invalid/qa-notes.txt",
            "content_type": "text/plain",
        },
    )
    updated_case = client.patch(f"/cases/{case['id']}", {"status": "in_review"})
    assert_true(updated_case["status"] == "in_review", "case status update failed")
    case_detail = client.get(f"/cases/{case['id']}")
    assert_true(len(case_detail["notes"]) >= 1, "case note missing")
    assert_true(len(case_detail["linked_entities"]) >= 1, "case entity missing")
    assert_true(len(case_detail["attachments"]) >= 1, "case attachment missing")
    results.append(CheckResult("case create/enrich/update", True, f"case_id={case['id']} notes={len(case_detail['notes'])} entities={len(case_detail['linked_entities'])}"))

    log("[workflow] watchlist cleanup")
    watch_id = watch_entry_value["id"]
    removed = client.delete(f"/watchlist/{watch_id}")
    assert_true(removed["removed"] is True, "watchlist cleanup failed")
    results.append(CheckResult("watchlist cleanup", True, f"entry_id={watch_id}"))

    return results



def main() -> int:
    client = ApiClient(BASE_URL)
    results: List[CheckResult] = []
    failures: List[str] = []

    try:
        log("[auth] login")
        client.login()
        results.append(CheckResult("login", True, LOGIN_EMAIL))
    except Exception as exc:
        print(json.dumps({"results": [], "failures": [f"login failed: {exc}"]}, indent=2))
        return 1

    payloads: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = {}

    for wallet in REAL_WALLETS:
        try:
            wallet_results, enrich, intelligence, cluster = test_wallet_basics(client, wallet)
            results.extend(wallet_results)
            payloads[wallet["label"]] = (enrich, intelligence, cluster)
        except Exception as exc:
            failures.append(f"{wallet['label']}: {exc}")

    if "binance_hot" in payloads:
        enrich, intelligence, cluster = payloads["binance_hot"]
        try:
            results.extend(test_watchlist_alert_incident_case(client, enrich, intelligence, cluster))
        except Exception as exc:
            failures.append(f"workflow binance_hot: {exc}")

    log("[done] summarizing")
    print(json.dumps({
        "results": [result.__dict__ for result in results],
        "failures": failures,
    }, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
