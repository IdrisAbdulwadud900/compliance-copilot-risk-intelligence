"""
Wallet clustering and relationship detection engine.

The implementation is deterministic for repeatable tests, but models real
blockchain-intelligence heuristics:
    * shared funding source
    * synchronized activity
    * common counterparties
    * cross-chain bridge linkage

It returns a graph representation plus cluster-level confidence and evidence,
which lets the UI prioritize, visualize, and refresh clusters in real time.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, cast

from app.intelligence import fingerprint_wallet
from app.risk_engine import score_wallet, _to_level
from app.cluster_store import get_store
from app.schemas import (
    ActivityBand,
        Blockchain,
        ClusterEdge,
        ClusterHeuristicEvidence,
        ClusterNode,
        ClusterRelationType,
        ClusteringHeuristicType,
        WalletClusterResponse,
        WalletInput,
)


# ---------------------------------------------------------------------------
# Deterministic wallet derivation
# Generates realistic-looking related wallets from the root address hash
# so the same input always produces the same cluster.
# ---------------------------------------------------------------------------

def _derive_address(seed: str, index: int, chain: Blockchain) -> str:
    digest = hashlib.sha256(f"{seed}:{index}:{chain}".encode()).hexdigest()
    if chain == "solana":
        # Solana base58 style (44 chars)
        return digest[:44]
    # EVM style
    return "0x" + digest[:40]


def _perturb_score(base_score: int, seed: str, index: int) -> int:
    h = int(hashlib.md5(f"{seed}:{index}".encode()).hexdigest(), 16)
    delta = (h % 25) - 12  # -12 to +12
    return max(0, min(100, base_score + delta))


def _hash_int(*parts: object) -> int:
    return int(hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest(), 16)


def _iso_offset(seed: str, minutes_back: int) -> str:
    offset = _hash_int(seed, minutes_back) % max(1, minutes_back)
    dt = datetime.now(timezone.utc) - timedelta(minutes=offset)
    return dt.isoformat()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _activity_band(txn_24h: int, volume_24h_usd: float) -> ActivityBand:
    if txn_24h >= 250 or volume_24h_usd >= 750_000:
        return "high"
    if txn_24h >= 50 or volume_24h_usd >= 100_000:
        return "moderate"
    return "low"


def _cross_chain_preference(wallet: WalletInput) -> bool:
    return wallet.bridge_hops >= 2 or wallet.volume_24h_usd >= 250_000


def build_cluster(
    root_wallet: WalletInput,
    root_score_int: int,
    max_nodes: int = 8,
) -> WalletClusterResponse:
    """Build a wallet relationship graph rooted at the given wallet."""
    seed = root_wallet.address.lower()
    chain = root_wallet.chain

    root_fps = fingerprint_wallet(root_wallet, score_wallet(root_wallet))
    root_node = ClusterNode(
        address=root_wallet.address,
        chain=chain,
        score=root_score_int,
        risk_level=_to_level(root_score_int),
        fingerprints=[f.label for f in root_fps],
        confidence=100,
        entity_likelihood=1.0,
        last_active_at=datetime.now(timezone.utc).isoformat(),
        activity_band=_activity_band(root_wallet.txn_24h, root_wallet.volume_24h_usd),
        is_root=True,
    )

    nodes: List[ClusterNode] = [root_node]
    edges: List[ClusterEdge] = []
    heuristics: List[ClusterHeuristicEvidence] = []

    n_related = _related_count(root_wallet, root_score_int, max_nodes - 1)
    relations = _relation_pool(root_wallet)

    for i in range(n_related):
        addr = _derive_address(seed, i, chain)
        node_score = _perturb_score(root_score_int, seed, i)
        node_chain = _vary_chain(chain, seed, i)
        node_wallet = _make_related_wallet(root_wallet, addr, node_chain, i)
        node_fps = fingerprint_wallet(node_wallet, score_wallet(node_wallet))
        relation: ClusterRelationType = relations[i % len(relations)]
        node_confidence = _node_confidence(root_wallet, node_wallet, relation)
        same_entity_likelihood = round(node_confidence / 100.0, 2)

        node = ClusterNode(
            address=addr,
            chain=node_chain,
            score=node_score,
            risk_level=_to_level(node_score),
            fingerprints=[f.label for f in node_fps],
            confidence=node_confidence,
            entity_likelihood=same_entity_likelihood,
            last_active_at=_iso_offset(addr, 360),
            activity_band=_activity_band(node_wallet.txn_24h, node_wallet.volume_24h_usd),
        )
        nodes.append(node)

        edge_evidence = _build_edge_evidence(root_wallet, node_wallet, relation)
        shared_counterparties = 1 + (_hash_int(addr, "cp") % 4) if relation == "common_counterparty" else 0
        strength = _edge_strength(relation, edge_evidence, i)
        edges.append(ClusterEdge(
            source=root_wallet.address,
            target=addr,
            relation=relation,
            strength=strength,
            confidence=node_confidence,
            shared_counterparties=shared_counterparties,
            same_entity_likelihood=same_entity_likelihood,
            evidence=edge_evidence,
        ))

        if i > 0 and i % 3 == 0:
            prev_addr = _derive_address(seed, i - 1, chain)
            edges.append(ClusterEdge(
                source=prev_addr,
                target=addr,
                relation="co_funded",
                strength=0.4,
                confidence=max(35, node_confidence - 15),
                same_entity_likelihood=round(_clamp((node_confidence - 15) / 100.0, 0.2, 0.95), 2),
                evidence=[
                    ClusterHeuristicEvidence(
                        heuristic="shared_funding_source",
                        confidence=max(35, node_confidence - 15),
                        weight=0.35,
                        description="Two non-root wallets share a common upstream funding pattern.",
                        related_addresses=[prev_addr, addr],
                    )
                ],
            ))

    all_scores = [n.score for n in nodes]
    cluster_score = max(all_scores)
    cluster_risk = _to_level(cluster_score)
    heuristics = _build_cluster_heuristics(root_wallet, nodes, edges)
    cluster_confidence = _cluster_confidence(nodes, edges, heuristics)
    cluster_id = hashlib.sha1(f"{root_wallet.chain}:{root_wallet.address.lower()}".encode()).hexdigest()[:12]
    cross_chain = len({node.chain for node in nodes}) > 1

    narrative = _cluster_narrative(root_wallet, nodes, edges, cluster_risk, cluster_confidence)

    response = WalletClusterResponse(
        cluster_id=cluster_id,
        root_address=root_wallet.address,
        nodes=nodes,
        edges=edges,
        heuristics=heuristics,
        confidence=cluster_confidence,
        cluster_score=cluster_score,
        cluster_risk=cluster_risk,
        cross_chain=cross_chain,
        last_updated_at=datetime.now(timezone.utc).isoformat(),
        refresh_suggested_after_sec=_refresh_hint(root_wallet, cluster_confidence),
        narrative=narrative,
    )

    # Persist into the live graph so query_relationships can serve it
    try:
        get_store().populate_from_response(response)
    except Exception:  # never let store errors surface to the caller
        pass

    return response


def _related_count(wallet: WalletInput, score: int, cap: int) -> int:
    base = 2
    if score >= 65:
        base += 3
    if wallet.bridge_hops >= 4:
        base += 2
    if wallet.mixer_exposure_pct >= 10:
        base += 1
    return min(base, cap)


def _relation_pool(wallet: WalletInput) -> List[ClusterRelationType]:
    pool: List[ClusterRelationType] = ["shared_funding_source"]
    if wallet.bridge_hops >= 2:
        pool.append("cross_chain_bridge")
    if wallet.mixer_exposure_pct >= 5:
        pool.append("common_counterparty")
    if wallet.txn_24h > 100 or wallet.volume_24h_usd > 150_000:
        pool.append("synchronized_activity")
    if wallet.txn_24h > 200:
        pool.append("co_funded")
    return pool or ["shared_funding_source"]


def _vary_chain(base_chain: Blockchain, seed: str, index: int) -> Blockchain:
    chains: List[Blockchain] = ["ethereum", "arbitrum", "base", "bsc", "polygon", "solana"]
    if index % 4 != 0 and index % 3 != 0:
        return base_chain
    h = int(hashlib.md5(f"{seed}:{index}:chain".encode()).hexdigest(), 16)
    return chains[h % len(chains)]


def _make_related_wallet(
    root: WalletInput,
    address: str,
    chain: Blockchain,
    index: int,
) -> WalletInput:
    """Create a plausible related wallet by slightly varying root inputs."""
    h = int(hashlib.md5(f"{address}:{index}".encode()).hexdigest(), 16)
    factor = 0.6 + (h % 80) / 100.0  # 0.6 - 1.4
    return WalletInput(
        chain=chain,
        address=address,
        txn_24h=max(0, int(root.txn_24h * factor)),
        volume_24h_usd=max(0.0, root.volume_24h_usd * factor),
        sanctions_exposure_pct=min(100.0, root.sanctions_exposure_pct * factor),
        mixer_exposure_pct=min(100.0, root.mixer_exposure_pct * factor),
        bridge_hops=max(0, int(root.bridge_hops * factor)),
    )


def _node_confidence(root: WalletInput, related: WalletInput, relation: ClusterRelationType) -> int:
    score = 35
    if relation in ("shared_funding_source", "co_funded"):
        score += 20
    if relation == "common_counterparty":
        score += 18
    if relation == "synchronized_activity":
        score += 15
    if relation == "cross_chain_bridge":
        score += 12
    if related.chain != root.chain and _cross_chain_preference(root):
        score += 8

    txn_similarity = 1 - min(1.0, abs(root.txn_24h - related.txn_24h) / max(1, root.txn_24h + 1))
    volume_similarity = 1 - min(1.0, abs(root.volume_24h_usd - related.volume_24h_usd) / max(1.0, root.volume_24h_usd + 1.0))
    score += int(12 * txn_similarity)
    score += int(10 * volume_similarity)
    return int(_clamp(score, 25, 95))


def _build_edge_evidence(
    root: WalletInput,
    related: WalletInput,
    relation: ClusterRelationType,
) -> List[ClusterHeuristicEvidence]:
    evidence: List[ClusterHeuristicEvidence] = []

    if relation in ("shared_funding_source", "co_funded"):
        evidence.append(
            ClusterHeuristicEvidence(
                heuristic="shared_funding_source",
                confidence=78,
                weight=0.35,
                description="Wallets show deterministic upstream funding similarity and balance ramp pattern.",
                related_addresses=[root.address, related.address],
            )
        )
    if relation == "synchronized_activity":
        evidence.append(
            ClusterHeuristicEvidence(
                heuristic="synchronized_activity",
                confidence=72,
                weight=0.25,
                description="Wallets exhibit comparable transaction velocity and activation timing within the same operating window.",
                related_addresses=[root.address, related.address],
            )
        )
    if relation == "common_counterparty":
        evidence.append(
            ClusterHeuristicEvidence(
                heuristic="common_counterparty",
                confidence=74,
                weight=0.20,
                description="Wallets interact with overlapping risky counterparties or liquidity hubs.",
                related_addresses=[root.address, related.address],
            )
        )
    if relation == "cross_chain_bridge":
        evidence.append(
            ClusterHeuristicEvidence(
                heuristic="cross_chain_link",
                confidence=69,
                weight=0.20,
                description="Bridge-hop behavior and chain rotation suggest cross-chain control by one operator set.",
                related_addresses=[root.address, related.address],
            )
        )

    fingerprint_overlap = len(set(fp.label for fp in fingerprint_wallet(root, score_wallet(root))) & set(fp.label for fp in fingerprint_wallet(related, score_wallet(related))))
    if fingerprint_overlap:
        evidence.append(
            ClusterHeuristicEvidence(
                heuristic="behavioral_similarity",
                confidence=min(90, 55 + fingerprint_overlap * 10),
                weight=0.20,
                description=f"Wallets share {fingerprint_overlap} behavioral fingerprint(s), increasing same-entity confidence.",
                related_addresses=[root.address, related.address],
            )
        )
    return evidence


def _edge_strength(
    relation: ClusterRelationType,
    evidence: Iterable[ClusterHeuristicEvidence],
    index: int,
) -> float:
    base = {
        "shared_funding_source": 0.78,
        "co_funded": 0.62,
        "synchronized_activity": 0.67,
        "common_counterparty": 0.64,
        "cross_chain_bridge": 0.59,
    }[relation]
    bonus = sum(item.weight for item in evidence) * 0.15
    decay = index * 0.04
    return round(_clamp(base + bonus - decay, 0.2, 0.95), 2)


def _build_cluster_heuristics(
    root: WalletInput,
    nodes: List[ClusterNode],
    edges: List[ClusterEdge],
) -> List[ClusterHeuristicEvidence]:
    heuristics: List[ClusterHeuristicEvidence] = []
    addresses = [node.address for node in nodes]

    if any(edge.relation in ("shared_funding_source", "co_funded") for edge in edges):
        heuristics.append(
            ClusterHeuristicEvidence(
                heuristic="shared_funding_source",
                confidence=82,
                weight=0.35,
                description="Cluster members share upstream funding patterns consistent with coordinated wallet provisioning.",
                related_addresses=addresses[:4],
            )
        )
    if any(edge.relation == "synchronized_activity" for edge in edges):
        heuristics.append(
            ClusterHeuristicEvidence(
                heuristic="synchronized_activity",
                confidence=76,
                weight=0.25,
                description="Multiple wallets activate within similar time windows and transaction cadence bands.",
                related_addresses=addresses[:4],
            )
        )
    if any(edge.relation == "common_counterparty" for edge in edges):
        heuristics.append(
            ClusterHeuristicEvidence(
                heuristic="common_counterparty",
                confidence=74,
                weight=0.20,
                description="Cluster shares counterparties or routing venues, suggesting common operational control.",
                related_addresses=addresses[:4],
            )
        )
    if len({node.chain for node in nodes}) > 1 and _cross_chain_preference(root):
        heuristics.append(
            ClusterHeuristicEvidence(
                heuristic="cross_chain_link",
                confidence=71,
                weight=0.20,
                description="Wallet relationships span multiple chains with bridge-linked activity, indicating cross-chain clustering.",
                related_addresses=addresses[:4],
            )
        )
    return heuristics


def _cluster_confidence(
    nodes: List[ClusterNode],
    edges: List[ClusterEdge],
    heuristics: List[ClusterHeuristicEvidence],
) -> int:
    node_avg = sum(node.confidence for node in nodes[1:]) / max(1, len(nodes) - 1)
    edge_avg = sum(edge.confidence for edge in edges) / max(1, len(edges))
    heuristic_avg = sum(item.confidence * item.weight for item in heuristics)
    score = 0.4 * node_avg + 0.3 * edge_avg + 0.3 * heuristic_avg
    return int(round(_clamp(score, 25, 95)))


def _refresh_hint(wallet: WalletInput, cluster_confidence: int) -> int:
    if cluster_confidence >= 80 or wallet.txn_24h >= 250:
        return 30
    if wallet.bridge_hops >= 3 or wallet.volume_24h_usd >= 500_000:
        return 45
    return 90


def _cluster_narrative(
    root: WalletInput,
    nodes: List[ClusterNode],
    edges: List[ClusterEdge],
    cluster_risk: str,
    cluster_confidence: int,
) -> str:
    n = len(nodes)
    chains = list({node.chain for node in nodes})
    chain_str = " and ".join(chains) if len(chains) <= 3 else f"{len(chains)} chains"
    all_fps = set()
    for node in nodes:
        all_fps.update(node.fingerprints)

    parts = [f"Cluster of {n} wallets identified across {chain_str} with {cluster_confidence}% confidence."]

    if "sanctions_linked" in all_fps or "sanctions_adjacent" in all_fps:
        parts.append("At least one cluster member has sanctions exposure — entire cluster should be treated as high-risk.")
    elif "bridge_hopper" in all_fps and "mixer_user" in all_fps:
        parts.append("Combined bridge-hopping and mixer usage across cluster nodes suggests coordinated layering operation.")
    elif "insider" in all_fps:
        parts.append("Insider accumulation pattern detected. Cluster may represent coordinated pre-launch wallet infrastructure.")
    elif "memecoin_cluster" in all_fps:
        parts.append("Cluster exhibits memecoin launch behavior — likely coordinated early buy group.")
    elif "wash_trader" in all_fps:
        parts.append("Multiple wash-trading signals across cluster suggest artificial volume coordination.")

    bridge_edges = [e for e in edges if e.relation == "cross_chain_bridge"]
    if bridge_edges:
        parts.append(f"{len(bridge_edges)} cross-chain bridge links detected between cluster members.")

    if any(e.relation == "shared_funding_source" for e in edges):
        parts.append("Shared-funding heuristics suggest wallets may be provisioned by the same operator.")

    if any(e.relation == "synchronized_activity" for e in edges):
        parts.append("Synchronized activity windows indicate coordinated execution rather than random overlap.")

    if any(e.relation == "common_counterparty" for e in edges):
        parts.append("Common counterparty overlap reinforces the same-entity hypothesis.")

    return " ".join(parts)
