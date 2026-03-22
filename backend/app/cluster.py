"""
Wallet Cluster Engine
---------------------
Deterministically generates a related-wallet graph based on a root
wallet's behavioral signals. In production this would query a graph DB
or on-chain data provider; here we derive it from the risk signal itself
to produce meaningful and consistent cluster intelligence.
"""

import hashlib
from typing import List, Tuple

from app.intelligence import fingerprint_wallet, detect_narrative
from app.risk_engine import score_wallet, _to_level
from app.schemas import (
    Blockchain,
    ClusterEdge,
    ClusterNode,
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
    """Slightly vary the score for related wallets deterministically."""
    h = int(hashlib.md5(f"{seed}:{index}".encode()).hexdigest(), 16)
    delta = (h % 25) - 12  # -12 to +12
    return max(0, min(100, base_score + delta))


def build_cluster(
    root_wallet: WalletInput,
    root_score_int: int,
    max_nodes: int = 8,
) -> WalletClusterResponse:
    """
    Build a wallet cluster graph rooted at the given wallet.
    Returns nodes, edges, and a cluster-level risk narrative.
    """
    seed = root_wallet.address.lower()
    chain = root_wallet.chain

    # --- Root node ---
    root_fps = fingerprint_wallet(root_wallet, score_wallet(root_wallet))
    root_node = ClusterNode(
        address=root_wallet.address,
        chain=chain,
        score=root_score_int,
        risk_level=_to_level(root_score_int),
        fingerprints=[f.label for f in root_fps],
        is_root=True,
    )

    nodes: List[ClusterNode] = [root_node]
    edges: List[ClusterEdge] = []

    # --- Derive related wallets ---
    # Number of related wallets scales with risk signal strength
    n_related = _related_count(root_wallet, root_score_int, max_nodes - 1)
    relations = _relation_pool(root_wallet)

    for i in range(n_related):
        addr = _derive_address(seed, i, chain)
        node_score = _perturb_score(root_score_int, seed, i)

        # Vary chain for cross-chain clusters
        node_chain = _vary_chain(chain, seed, i)

        # Build a minimal WalletInput for fingerprinting
        node_wallet = _make_related_wallet(root_wallet, addr, node_chain, i)
        node_fps = fingerprint_wallet(node_wallet, score_wallet(node_wallet))

        node = ClusterNode(
            address=addr,
            chain=node_chain,
            score=node_score,
            risk_level=_to_level(node_score),
            fingerprints=[f.label for f in node_fps],
        )
        nodes.append(node)

        relation = relations[i % len(relations)]
        strength = round(0.9 - (i * 0.08), 2)
        edges.append(ClusterEdge(
            source=root_wallet.address,
            target=addr,
            relation=relation,
            strength=max(0.2, strength),
        ))

        # Cross-links between related nodes for denser graph
        if i > 0 and i % 3 == 0:
            prev_addr = _derive_address(seed, i - 1, chain)
            edges.append(ClusterEdge(
                source=prev_addr,
                target=addr,
                relation="co_funded",
                strength=0.4,
            ))

    # --- Cluster risk level = highest node risk ---
    all_scores = [n.score for n in nodes]
    cluster_score = max(all_scores)
    cluster_risk = _to_level(cluster_score)

    narrative = _cluster_narrative(root_wallet, nodes, edges, cluster_risk)

    return WalletClusterResponse(
        root_address=root_wallet.address,
        nodes=nodes,
        edges=edges,
        cluster_risk=cluster_risk,
        narrative=narrative,
    )


def _related_count(wallet: WalletInput, score: int, cap: int) -> int:
    base = 2
    if score >= 65:
        base += 3
    if wallet.bridge_hops >= 4:
        base += 2
    if wallet.mixer_exposure_pct >= 10:
        base += 1
    return min(base, cap)


def _relation_pool(wallet: WalletInput) -> List[str]:
    pool = ["co_funded"]
    if wallet.bridge_hops >= 2:
        pool.append("bridge_hop")
    if wallet.mixer_exposure_pct >= 5:
        pool.append("common_counterparty")
    if wallet.txn_24h > 100:
        pool.append("co_funded")
    return pool or ["co_funded"]


def _vary_chain(base_chain: Blockchain, seed: str, index: int) -> Blockchain:
    chains: List[Blockchain] = ["ethereum", "arbitrum", "base", "bsc", "polygon", "solana"]
    if index % 4 != 0:
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


def _cluster_narrative(
    root: WalletInput,
    nodes: List[ClusterNode],
    edges: List[ClusterEdge],
    cluster_risk: str,
) -> str:
    n = len(nodes)
    chains = list({node.chain for node in nodes})
    chain_str = " and ".join(chains) if len(chains) <= 3 else f"{len(chains)} chains"
    all_fps = set()
    for node in nodes:
        all_fps.update(node.fingerprints)

    parts = [f"Cluster of {n} wallets identified across {chain_str}."]

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

    bridge_edges = [e for e in edges if e.relation == "bridge_hop"]
    if bridge_edges:
        parts.append(f"{len(bridge_edges)} bridge-hop links detected between cluster members.")

    return " ".join(parts)
