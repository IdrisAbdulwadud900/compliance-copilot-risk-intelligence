from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.schemas import Blockchain, WalletEnrichmentResponse


_USER_AGENT = "ComplianceCopilot/0.2"
_HTTP_TIMEOUT_SECONDS = 15
_MAX_TX_PAGES = 4
_WEI_PER_ETH = Decimal("1000000000000000000")
_ETHEREUM_BLOCKSCOUT_BASE = "https://eth.blockscout.com/api/v2"
_COINGECKO_ETH_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"


def _fetch_json(url: str) -> Dict[str, Any]:
    request = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _parse_decimal(raw: Any) -> Decimal:
    if raw in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _parse_timestamp(raw: str) -> datetime:
    normalized = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _ethereum_price_usd(address_payload: Dict[str, Any]) -> Decimal:
    embedded_rate = _parse_decimal(address_payload.get("exchange_rate"))
    if embedded_rate > 0:
        return embedded_rate

    payload = _fetch_json(_COINGECKO_ETH_PRICE_URL)
    return _parse_decimal(payload.get("ethereum", {}).get("usd"))


def _scan_recent_eth_transactions(address: str) -> tuple[int, Decimal, int, bool]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    endpoint = f"{_ETHEREUM_BLOCKSCOUT_BASE}/addresses/{address}/transactions"

    params: Optional[Dict[str, Any]] = None
    tx_count = 0
    total_wei = Decimal("0")
    scanned = 0
    partial = False

    for _ in range(_MAX_TX_PAGES):
        url = endpoint if not params else f"{endpoint}?{urlencode(params)}"
        try:
            payload = _fetch_json(url)
        except (HTTPError, URLError, TimeoutError):
            if scanned > 0:
                partial = True
                break
            raise
        items = payload.get("items", [])
        if not items:
            break

        reached_older_records = False
        for item in items:
            scanned += 1
            timestamp_raw = item.get("timestamp")
            if not timestamp_raw:
                continue
            timestamp = _parse_timestamp(str(timestamp_raw))
            if timestamp < cutoff:
                reached_older_records = True
                break

            tx_count += 1
            total_wei += _parse_decimal(item.get("value"))

        if reached_older_records:
            break

        params = payload.get("next_page_params")
        if not params:
            break

    return tx_count, (total_wei / _WEI_PER_ETH), scanned, partial


def enrich_wallet_input_live(address: str, chain: Blockchain) -> WalletEnrichmentResponse:
    if chain != "ethereum":
        raise ValueError("Live enrichment currently supports ethereum only")

    address_payload = _fetch_json(f"{_ETHEREUM_BLOCKSCOUT_BASE}/addresses/{address}")
    price_usd = _ethereum_price_usd(address_payload)
    txn_24h, volume_native, scanned, partial = _scan_recent_eth_transactions(address)

    balance_native = _parse_decimal(address_payload.get("coin_balance")) / _WEI_PER_ETH
    fetched_at = datetime.now(timezone.utc).isoformat()

    notes: List[str] = [
        "Live metrics are sourced from public Ethereum explorer data.",
        "Sanctions, mixer exposure, and bridge hops remain manual until a dedicated intel provider is configured.",
    ]
    if scanned >= _MAX_TX_PAGES * 50:
        notes.append("Recent transaction scan hit the page cap, so very high-activity wallets may be partially sampled.")
    if partial:
        notes.append("Explorer pagination failed during deep history scan, so the returned 24h metrics are a partial best-effort sample.")

    return WalletEnrichmentResponse(
        chain=chain,
        address=address,
        txn_24h=txn_24h,
        volume_24h_usd=round(float(volume_native * price_usd), 2),
        sanctions_exposure_pct=0,
        mixer_exposure_pct=0,
        bridge_hops=0,
        source="blockscout+coingecko",
        fetched_at=fetched_at,
        asset_price_usd=round(float(price_usd), 2),
        balance_native=round(float(balance_native), 6),
        recent_tx_scanned=scanned,
        live_supported=True,
        notes=notes,
    )