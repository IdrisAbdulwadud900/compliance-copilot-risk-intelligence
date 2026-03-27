from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from app.cluster_store import get_store
from app.intelligence import fingerprint_wallet
from app.live_wallet import (
    _ETHEREUM_BLOCKSCOUT_BASE,
    _MAX_TX_PAGES,
    _WEI_PER_ETH,
    _ethereum_price_usd,
    _fetch_json,
    _parse_decimal,
    _parse_timestamp,
)
from app.risk_engine import _to_level, score_wallet
from app.schemas import (
    ActivityBand,
    ClusterEdge,
    ClusterHeuristicEvidence,
    ClusterNode,
    ClusterRelationType,
    WalletClusterResponse,
    WalletInput,
)


@dataclass
class CounterpartyStat:
    address: str
    tx_count: int = 0
    in_count: int = 0
    out_count: int = 0
    volume_native: Decimal = Decimal("0")
    last_active_at: Optional[str] = None


def _activity_band(txn_24h: int, volume_24h_usd: float) -> ActivityBand:
    if txn_24h >= 250 or volume_24h_usd >= 750_000:
        return "high"
    if txn_24h >= 50 or volume_24h_usd >= 100_000:
        return "moderate"
    return "low"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _extract_counterparties(address: str) -> tuple[Dict[str, CounterpartyStat], int, bool]:
    lower_address = address.lower()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    endpoint = f"{_ETHEREUM_BLOCKSCOUT_BASE}/addresses/{address}/transactions"

    stats: Dict[str, CounterpartyStat] = {}
    params: Optional[Dict[str, object]] = None
    scanned = 0
    partial = False

    for _ in range(_MAX_TX_PAGES):
        url = endpoint if not params else f"{endpoint}?{urlencode(params)}"
        try:
            payload = _fetch_json(url)
        except (HTTPError, URLError, TimeoutError):
            partial = True
            break

        items = payload.get("items", [])
        if not items:
            break

        reached_older_records = False
        for item in items:
            timestamp_raw = item.get("timestamp")
            if not timestamp_raw:
                continue
            timestamp = _parse_timestamp(str(timestamp_raw))
            if timestamp < cutoff:
                reached_older_records = True
                break

            from_raw = item.get("from")
            to_raw = item.get("to")
            from_address = (from_raw or {}).get("hash") if isinstance(from_raw, dict) else from_raw
            to_address = (to_raw or {}).get("hash") if isinstance(to_raw, dict) else to_raw
            if not from_address and not to_address:
                continue

            from_lower = str(from_address or "").lower()
            to_lower = str(to_address or "").lower()
            if from_lower == lower_address and to_address:
                counterparty = str(to_address)
                incoming = False
            elif to_lower == lower_address and from_address:
                counterparty = str(from_address)
                incoming = True
            else:
                continue

            scanned += 1
            stat = stats.setdefault(counterparty.lower(), CounterpartyStat(address=counterparty))
            stat.tx_count += 1
            if incoming:
                stat.in_count += 1
            else:
                stat.out_count += 1
            stat.volume_native += _parse_decimal(item.get("value")) / _WEI_PER_ETH
            stat.last_active_at = timestamp.isoformat()

        if reached_older_records:
            break

        params = payload.get("next_page_params")
        if not params:
            break

    return stats, scanned, partial


def _relation_for(stat: CounterpartyStat) -> ClusterRelationType:
    if stat.in_count > 0 and stat.out_count > 0:
        return "common_counterparty"
    if stat.in_count > 0:
        return "shared_funding_source"
    if stat.tx_count >= 3:
        return "synchronized_activity"
    return "co_funded"


def _edge_confidence(stat: CounterpartyStat, volume_usd: float) -> int:
    score = 38 + min(26, stat.tx_count * 4)
    score += min(16, int(volume_usd / 150_000))
    if stat.in_count > 0 and stat.out_count > 0:
        score += 10
    return int(_clamp(score, 35, 92))


def _edge_strength(stat: CounterpartyStat, volume_usd: float) -> float:
    strength = 0.35 + min(0.35, stat.tx_count / 12) + min(0.2, volume_usd / 1_500_000)
    if stat.in_count > 0 and stat.out_count > 0:
        strength += 0.05
    return round(_clamp(strength, 0.2, 0.95), 2)


def _edge_evidence(root_wallet: WalletInput, related_wallet: WalletInput, stat: CounterpartyStat, relation: ClusterRelationType) -> List[ClusterHeuristicEvidence]:
    descriptions = {
        "shared_funding_source": "Counterparty funded the root wallet in recent on-chain activity, suggesting a direct funding relationship.",
        "common_counterparty": "Bidirectional flow with the root wallet indicates repeated direct interaction rather than a one-off transfer.",
        "synchronized_activity": "Multiple recent transfers in the same 24h window suggest operational coordination or routing cadence overlap.",
        "co_funded": "Recent transfer activity links the two wallets through direct value movement.",
    }
    heuristic_map = {
        "shared_funding_source": "shared_funding_source",
        "common_counterparty": "common_counterparty",
        "synchronized_activity": "synchronized_activity",
        "co_funded": "shared_funding_source",
    }
    confidence = _edge_confidence(stat, related_wallet.volume_24h_usd)
    evidence = [
        ClusterHeuristicEvidence(
            heuristic=heuristic_map[relation],  # type: ignore[arg-type]
            confidence=confidence,
            weight=0.35 if relation in ("shared_funding_source", "co_funded") else 0.25,
            description=descriptions[relation],
            related_addresses=[root_wallet.address, related_wallet.address],
        )
    ]
    root_fps = {fp.label for fp in fingerprint_wallet(root_wallet, score_wallet(root_wallet))}
    related_fps = {fp.label for fp in fingerprint_wallet(related_wallet, score_wallet(related_wallet))}
    overlap = sorted(root_fps & related_fps)
    if overlap:
        evidence.append(
            ClusterHeuristicEvidence(
                heuristic="behavioral_similarity",
                confidence=min(88, 58 + len(overlap) * 8),
                weight=0.2,
                description=f"Wallets share behavioral signals: {', '.join(overlap[:3])}.",
                related_addresses=[root_wallet.address, related_wallet.address],
            )
        )
    return evidence


def build_live_cluster(root_wallet: WalletInput, root_score_int: int, max_nodes: int = 6) -> Optional[WalletClusterResponse]:
    if root_wallet.chain != "ethereum":
        return None

    address_payload = _fetch_json(f"{_ETHEREUM_BLOCKSCOUT_BASE}/addresses/{root_wallet.address}")
    eth_price_usd = _ethereum_price_usd(address_payload)
    stats_map, scanned, partial = _extract_counterparties(root_wallet.address)
    ranked = sorted(
        stats_map.values(),
        key=lambda stat: (stat.tx_count, float(stat.volume_native), stat.in_count + stat.out_count),
        reverse=True,
    )[: max(1, max_nodes - 1)]

    root_fps = fingerprint_wallet(root_wallet, score_wallet(root_wallet))
    nodes: List[ClusterNode] = [
        ClusterNode(
            address=root_wallet.address,
            chain=root_wallet.chain,
            score=root_score_int,
            risk_level=_to_level(root_score_int),
            fingerprints=[fp.label for fp in root_fps],
            confidence=100,
            entity_likelihood=1.0,
            last_active_at=datetime.now(timezone.utc).isoformat(),
            activity_band=_activity_band(root_wallet.txn_24h, root_wallet.volume_24h_usd),
            is_root=True,
        )
    ]
    edges: List[ClusterEdge] = []
    heuristics: List[ClusterHeuristicEvidence] = []

    if not stats_map:
        narrative = (
            "Live Ethereum cluster found no recent counterparties in the last 24h, "
            "so the graph currently shows only the root wallet."
        )
        if partial:
            narrative += " Explorer sampling was partial during collection."

        response = WalletClusterResponse(
            cluster_id=hashlib.sha1(f"live:ethereum:{root_wallet.address.lower()}".encode()).hexdigest()[:12],
            root_address=root_wallet.address,
            nodes=nodes,
            edges=edges,
            heuristics=heuristics,
            confidence=55,
            cluster_score=root_score_int,
            cluster_risk=_to_level(root_score_int),
            cross_chain=False,
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            refresh_suggested_after_sec=120,
            narrative=narrative,
        )
        try:
            get_store().populate_from_response(response)
        except Exception:
            pass
        return response

    for stat in ranked:
        volume_usd = round(float(stat.volume_native * eth_price_usd), 2)
        related_wallet = WalletInput(
            chain="ethereum",
            address=stat.address,
            txn_24h=stat.tx_count,
            volume_24h_usd=volume_usd,
            sanctions_exposure_pct=0,
            mixer_exposure_pct=0,
            bridge_hops=0,
        )
        related_score = score_wallet(related_wallet)
        related_fps = fingerprint_wallet(related_wallet, related_score)
        relation = _relation_for(stat)
        confidence = _edge_confidence(stat, volume_usd)
        evidence = _edge_evidence(root_wallet, related_wallet, stat, relation)

        nodes.append(
            ClusterNode(
                address=stat.address,
                chain="ethereum",
                score=related_score.score,
                risk_level=related_score.risk_level,
                fingerprints=[fp.label for fp in related_fps],
                confidence=confidence,
                entity_likelihood=round(confidence / 100.0, 2),
                last_active_at=stat.last_active_at,
                activity_band=_activity_band(stat.tx_count, volume_usd),
                is_root=False,
            )
        )
        edges.append(
            ClusterEdge(
                source=root_wallet.address,
                target=stat.address,
                relation=relation,
                strength=_edge_strength(stat, volume_usd),
                confidence=confidence,
                shared_counterparties=max(0, min(5, stat.tx_count - 1)) if relation == "common_counterparty" else 0,
                same_entity_likelihood=round(confidence / 100.0, 2),
                evidence=evidence,
            )
        )

    addresses = [node.address for node in nodes]
    if any(edge.relation in ("shared_funding_source", "co_funded") for edge in edges):
        heuristics.append(
            ClusterHeuristicEvidence(
                heuristic="shared_funding_source",
                confidence=78,
                weight=0.35,
                description="Recent inbound or direct funding relationships connect the cluster to the root wallet.",
                related_addresses=addresses[:4],
            )
        )
    if any(edge.relation == "common_counterparty" for edge in edges):
        heuristics.append(
            ClusterHeuristicEvidence(
                heuristic="common_counterparty",
                confidence=74,
                weight=0.25,
                description="Bidirectional on-chain counterparties indicate repeated operational interaction.",
                related_addresses=addresses[:4],
            )
        )
    if any(edge.relation == "synchronized_activity" for edge in edges):
        heuristics.append(
            ClusterHeuristicEvidence(
                heuristic="synchronized_activity",
                confidence=72,
                weight=0.2,
                description="Multiple recent transfers landed in the same operating window, suggesting coordinated activity.",
                related_addresses=addresses[:4],
            )
        )

    cluster_score = max(node.score for node in nodes)
    edge_avg = sum(edge.confidence for edge in edges) / max(1, len(edges))
    heuristic_avg = sum(item.confidence * item.weight for item in heuristics)
    cluster_confidence = int(round(_clamp(edge_avg * 0.65 + heuristic_avg * 0.35, 35, 90)))
    narrative = (
        f"Live Ethereum cluster built from {len(ranked)} recent counterparties observed in the last 24h. "
        f"Scanned {scanned} recent transactions and identified the strongest relationships through direct value flow and repeated interactions."
    )
    if partial:
        narrative += " Data collection was partially sampled because explorer pagination failed on deep history."

    response = WalletClusterResponse(
        cluster_id=hashlib.sha1(f"live:ethereum:{root_wallet.address.lower()}".encode()).hexdigest()[:12],
        root_address=root_wallet.address,
        nodes=nodes,
        edges=edges,
        heuristics=heuristics,
        confidence=cluster_confidence,
        cluster_score=cluster_score,
        cluster_risk=_to_level(cluster_score),
        cross_chain=False,
        last_updated_at=datetime.now(timezone.utc).isoformat(),
        refresh_suggested_after_sec=45 if scanned >= 50 else 90,
        narrative=narrative,
    )

    try:
        get_store().populate_from_response(response)
    except Exception:
        pass

    return response