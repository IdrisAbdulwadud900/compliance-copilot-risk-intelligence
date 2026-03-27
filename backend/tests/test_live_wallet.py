from urllib.error import HTTPError

from app.live_wallet import enrich_wallet_input_live


def test_enrich_wallet_input_live_degrades_to_partial_sample(monkeypatch):
    calls: list[str] = []
    address = "0xbusy000000000000000000000000000000000001"

    def fake_fetch_json(url: str):
        calls.append(url)
        if url.endswith(f"/addresses/{address}"):
            return {
                "coin_balance": "1000000000000000000",
                "exchange_rate": "2000.0",
            }
        if url.endswith(f"/addresses/{address}/transactions"):
            return {
                "items": [
                    {
                        "timestamp": "2026-03-26T20:00:00.000000Z",
                        "value": "500000000000000000",
                    }
                ],
                "next_page_params": {"block_number": 1, "index": 1},
            }
        raise HTTPError(url=url, code=422, msg="unprocessable", hdrs=None, fp=None)

    monkeypatch.setattr("app.live_wallet._fetch_json", fake_fetch_json)

    enriched = enrich_wallet_input_live(address, "ethereum")

    assert enriched.txn_24h == 1
    assert enriched.volume_24h_usd == 1000.0
    assert enriched.recent_tx_scanned == 1
    assert any("partial best-effort sample" in note for note in enriched.notes)
    assert len(calls) >= 3