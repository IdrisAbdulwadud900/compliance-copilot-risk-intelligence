"""cluster_store.py — Domain-level clustering API.

This module owns the process-singleton ``ClusterIndex`` and exposes three
clean, composable functions:

    add_transaction(txn)          — ingest a new wallet interaction
    update_cluster(cluster_id)    — recompute a cluster from a ``WalletClusterResponse``
    query_relationships(address)  — explore the graph around a wallet

It also provides:

    populate_from_response(response)  — load a full ``WalletClusterResponse``
                                        into the store (called by build_cluster)
    get_cluster_meta(cluster_id)      — lightweight cluster summary
    find_wallet_cluster(address)      — which cluster does this wallet belong to?

Thread safety
─────────────
All public functions acquire the underlying ``ClusterIndex`` lock before
mutating state, so they are safe to call concurrently from FastAPI request
handlers.

Performance notes
─────────────────
* ``add_transaction`` is O(1) for existing nodes; O(log N) for new nodes
  (deque append + dict insert).
* ``query_relationships`` is O(V + E) in the worst case (full BFS), but
  bounded by ``max_depth`` so in practice it stays O(1) for small depth.
* The process-level singleton avoids per-request graph reconstruction.
  For multi-process deployments, replace with a Redis-backed graph
  (e.g. RedisGraph / Memgraph) behind the same interface.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.graph import ClusterIndex, ClusterMeta, EdgeMeta, NodeMeta

logger = logging.getLogger(__name__)

# ── Singleton store ───────────────────────────────────────────────────────────

_store: Optional["ClusterStore"] = None
_store_lock = threading.Lock()


def get_store() -> "ClusterStore":
    """Return the process-singleton ``ClusterStore`` (lazy-initialised)."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = ClusterStore()
    return _store


# ── Transaction input model ───────────────────────────────────────────────────

@dataclass
class TransactionRecord:
    """Minimal representation of a single wallet interaction.

    This is deliberately decoupled from ``WalletInput`` so the store can
    accept raw blockchain transaction data without requiring a full risk
    analysis pass.

    Args:
        source:         Sending wallet address.
        target:         Receiving wallet address.
        chain:          Blockchain identifier (e.g. "ethereum").
        volume_usd:     USD-equivalent transfer amount.
        relation:       Semantic relationship label (defaults to
                        ``"shared_funding_source"``).
        timestamp:      ISO-8601 UTC timestamp (defaults to now).
        strength:       Edge strength hint from the caller (0–1).
        source_score:   Pre-computed risk score for the source wallet (0–100).
        target_score:   Pre-computed risk score for the target wallet (0–100).
    """

    source: str
    target: str
    chain: str = "ethereum"
    volume_usd: float = 0.0
    relation: str = "shared_funding_source"
    timestamp: Optional[str] = None
    strength: float = 0.5
    source_score: int = 0
    target_score: int = 0

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# ── Relationship query result ─────────────────────────────────────────────────

@dataclass
class RelationshipResult:
    """Result returned by ``query_relationships``.

    Attributes:
        address:          The queried wallet address.
        cluster_id:       The cluster this wallet belongs to (None if unknown).
        direct_neighbors: Addresses one hop away (outgoing).
        predecessors:     Addresses one hop away (incoming).
        reachable:        All addresses reachable within *max_depth* hops.
        common_with:      Shared neighbors between this wallet and *compare_to*
                          (empty list when *compare_to* is ``None``).
        path_to:          Shortest directed path to *path_target* (empty list
                          when unreachable or *path_target* is ``None``).
        edges_out:        Outgoing edge metadata, sorted by confidence desc.
        edges_in:         Incoming edge metadata, sorted by confidence desc.
    """

    address: str
    cluster_id: Optional[str] = None
    direct_neighbors: List[str] = field(default_factory=list)
    predecessors: List[str] = field(default_factory=list)
    reachable: List[str] = field(default_factory=list)
    common_with: List[str] = field(default_factory=list)
    path_to: List[str] = field(default_factory=list)
    edges_out: List[EdgeMeta] = field(default_factory=list)
    edges_in: List[EdgeMeta] = field(default_factory=list)


# ── ClusterStore ──────────────────────────────────────────────────────────────

class ClusterStore:
    """Domain-level facade over a ``ClusterIndex``.

    The three primary operations match the spec:
        add_transaction    → mutate the graph with new interaction data
        update_cluster     → rebuild cluster metadata from a cluster response
        query_relationships → read traversal results for a given wallet
    """

    def __init__(self, max_nodes_per_cluster: int = 10_000) -> None:
        self._index = ClusterIndex(max_nodes_per_cluster=max_nodes_per_cluster)

    # ── 1. add_transaction ────────────────────────────────────────────────────

    def add_transaction(self, txn: TransactionRecord) -> None:
        """Ingest a new wallet interaction into the graph.

        Behaviour:
        * If both wallets already belong to the same cluster → reinforce the
          edge between them (confidence +2, strength +0.02, hit_count +1).
        * If one wallet is in a cluster and the other is not → add the
          newcomer to the existing cluster.
        * If the two wallets are in *different* clusters and the resulting
          confidence exceeds ``MERGE_THRESHOLD`` → merge the smaller into
          the larger.
        * If neither wallet is known → create a new cluster for this pair.

        Args:
            txn: A ``TransactionRecord`` describing the interaction.
        """
        ts = txn.timestamp or datetime.now(timezone.utc).isoformat()
        src_cluster = self._index.find_cluster(txn.source)
        dst_cluster = self._index.find_cluster(txn.target)

        if src_cluster is None and dst_cluster is None:
            # Entirely new pair — bootstrap a cluster
            cluster_id = _derive_cluster_id(txn.source, txn.chain)
            root_meta = NodeMeta(
                address=txn.source,
                chain=txn.chain,
                score=txn.source_score,
                confidence=50,
                last_active_at=ts,
            )
            cluster_meta = ClusterMeta(
                cluster_id=cluster_id,
                root_address=txn.source,
                confidence=50,
                last_updated_at=ts,
            )
            g = self._index.create_cluster(cluster_id, root_meta, cluster_meta)

            target_meta = NodeMeta(
                address=txn.target,
                chain=txn.chain,
                score=txn.target_score,
                confidence=50,
                last_active_at=ts,
            )
            self._index.add_node_to_cluster(cluster_id, target_meta)
            edge = EdgeMeta(
                source=txn.source,
                target=txn.target,
                relation=txn.relation,
                strength=txn.strength,
                confidence=50,
            )
            g.add_edge(edge)
            logger.debug("Created cluster %r for new pair %s→%s", cluster_id, txn.source, txn.target)

        elif src_cluster is not None and dst_cluster is None:
            # Add target to the existing source cluster
            self._add_wallet_to_cluster(src_cluster, txn.target, txn.chain, txn.target_score, ts)
            g = self._index.get_graph(src_cluster)
            if g:
                g.add_edge(EdgeMeta(
                    source=txn.source,
                    target=txn.target,
                    relation=txn.relation,
                    strength=txn.strength,
                    confidence=50,
                ))
            self._touch_cluster(src_cluster, ts)

        elif src_cluster is None and dst_cluster is not None:
            # Add source to the existing destination cluster
            self._add_wallet_to_cluster(dst_cluster, txn.source, txn.chain, txn.source_score, ts)
            g = self._index.get_graph(dst_cluster)
            if g:
                g.add_edge(EdgeMeta(
                    source=txn.source,
                    target=txn.target,
                    relation=txn.relation,
                    strength=txn.strength,
                    confidence=50,
                ))
            self._touch_cluster(dst_cluster, ts)

        elif src_cluster == dst_cluster:
            # Same cluster — reinforce existing edge (or add new one)
            g = self._index.get_graph(src_cluster)
            if g:
                src_node = g.get_node(txn.source)
                if src_node:
                    src_node.update_activity(txn.volume_usd, ts)
                dst_node = g.get_node(txn.target)
                if dst_node:
                    dst_node.update_activity(txn.volume_usd, ts)
                g.add_edge(EdgeMeta(
                    source=txn.source,
                    target=txn.target,
                    relation=txn.relation,
                    strength=txn.strength,
                    confidence=50,
                ))
            self._touch_cluster(src_cluster, ts)  # type: ignore[arg-type]

        else:
            # Different clusters — potentially merge
            assert src_cluster is not None and dst_cluster is not None
            self._handle_cross_cluster_txn(src_cluster, dst_cluster, txn, ts)

    # ── 2. update_cluster ─────────────────────────────────────────────────────

    def update_cluster(self, cluster_id: str, **meta_updates: object) -> None:
        """Recompute and persist cluster-level metadata.

        Callers can pass any ``ClusterMeta`` fields as keyword arguments.
        The cluster confidence score is always recomputed from the live graph.

        Example::

            store.update_cluster(
                cluster_id,
                cluster_score=92,
                narrative="High-risk cluster with mixer linkage.",
            )

        Args:
            cluster_id:    The cluster to update.
            **meta_updates: Any ``ClusterMeta`` field → value mappings.

        Raises:
            KeyError: If the cluster does not exist.
        """
        # Always recompute live confidence; callers may also pass last_updated_at
        # so we normalise it here to avoid duplicate-kwarg errors.
        live_confidence = self._index.compute_confidence(cluster_id)
        normalised = {k: v for k, v in meta_updates.items() if k != "last_updated_at"}
        self._index.update_meta(
            cluster_id,
            confidence=live_confidence,
            last_updated_at=datetime.now(timezone.utc).isoformat(),
            **normalised,
        )
        logger.debug("Updated cluster %r — confidence=%d", cluster_id, live_confidence)

    # ── 3. query_relationships ────────────────────────────────────────────────

    def query_relationships(
        self,
        address: str,
        max_depth: int = 3,
        min_edge_confidence: int = 0,
        compare_to: Optional[str] = None,
        path_target: Optional[str] = None,
    ) -> RelationshipResult:
        """Return the graph neighbourhood of *address*.

        Args:
            address:             Wallet to explore.
            max_depth:           BFS depth limit (default 3, max 6).
            min_edge_confidence: Only traverse edges with confidence ≥ this
                                 value (0 = all edges).
            compare_to:          If provided, return common neighbours between
                                 *address* and this wallet.
            path_target:         If provided, return the shortest directed path
                                 from *address* to this wallet.

        Returns:
            A ``RelationshipResult`` dataclass.
        """
        max_depth = min(max_depth, 6)
        cluster_id = self._index.find_cluster(address)
        if cluster_id is None:
            return RelationshipResult(address=address)

        g = self._index.get_graph(cluster_id)
        if g is None:
            return RelationshipResult(address=address, cluster_id=cluster_id)

        confidence_filter = None
        if min_edge_confidence > 0:
            confidence_filter = lambda e: e.confidence >= min_edge_confidence  # noqa: E731

        neighbors = g.neighbors(address)
        preds = g.predecessors(address)
        reachable = g.bfs(address, max_depth=max_depth, filter_fn=confidence_filter)
        edges_out = sorted(g.edges_from(address), key=lambda e: e.confidence, reverse=True)
        edges_in = sorted(g.edges_to(address), key=lambda e: e.confidence, reverse=True)
        common = g.common_neighbors(address, compare_to) if compare_to else []
        path = g.shortest_path(address, path_target) if path_target else []

        return RelationshipResult(
            address=address,
            cluster_id=cluster_id,
            direct_neighbors=neighbors,
            predecessors=preds,
            reachable=reachable,
            common_with=common,
            path_to=path,
            edges_out=edges_out,
            edges_in=edges_in,
        )

    # ── populate_from_response ────────────────────────────────────────────────

    def populate_from_response(self, response: object) -> None:
        """Load a ``WalletClusterResponse`` into the store.

        This is the bridge between the deterministic ``build_cluster`` engine
        and the live graph.  Calling this after ``build_cluster`` ensures the
        returned cluster is immediately queryable via ``query_relationships``.

        Args:
            response: A ``WalletClusterResponse`` Pydantic model instance.
        """
        # Import here to avoid circular imports at module load time
        from app.schemas import WalletClusterResponse  # noqa: PLC0415

        if not isinstance(response, WalletClusterResponse):
            raise TypeError(f"Expected WalletClusterResponse, got {type(response)!r}")

        cluster_id = response.cluster_id
        now = datetime.now(timezone.utc).isoformat()

        # Determine root node
        root_schema_node = next((n for n in response.nodes if n.is_root), response.nodes[0])

        root_node = NodeMeta(
            address=root_schema_node.address,
            chain=root_schema_node.chain,
            score=root_schema_node.score,
            risk_level=root_schema_node.risk_level,
            confidence=root_schema_node.confidence,
            entity_likelihood=root_schema_node.entity_likelihood,
            activity_band=root_schema_node.activity_band,
            last_active_at=root_schema_node.last_active_at or now,
        )

        cluster_meta = ClusterMeta(
            cluster_id=cluster_id,
            root_address=response.root_address,
            confidence=response.confidence,
            cluster_score=response.cluster_score,
            cross_chain=response.cross_chain,
            heuristics=[h.heuristic for h in response.heuristics],
            narrative=response.narrative,
            last_updated_at=response.last_updated_at,
            refresh_suggested_after_sec=response.refresh_suggested_after_sec,
        )

        # Create or reuse cluster
        existing = self._index.get_graph(cluster_id)
        if existing is None:
            self._index.create_cluster(cluster_id, root_node, cluster_meta)
        else:
            self._index.add_node_to_cluster(cluster_id, root_node)
            self._index.update_meta(
                cluster_id,
                confidence=response.confidence,
                cluster_score=response.cluster_score,
                cross_chain=response.cross_chain,
                narrative=response.narrative,
                last_updated_at=response.last_updated_at,
            )

        # Insert remaining nodes
        for schema_node in response.nodes:
            if schema_node.address == root_schema_node.address:
                continue
            node = NodeMeta(
                address=schema_node.address,
                chain=schema_node.chain,
                score=schema_node.score,
                risk_level=schema_node.risk_level,
                confidence=schema_node.confidence,
                entity_likelihood=schema_node.entity_likelihood,
                activity_band=schema_node.activity_band,
                last_active_at=schema_node.last_active_at or now,
            )
            self._index.add_node_to_cluster(cluster_id, node)

        # Insert edges
        g = self._index.get_graph(cluster_id)
        if g:
            for schema_edge in response.edges:
                edge = EdgeMeta(
                    source=schema_edge.source,
                    target=schema_edge.target,
                    relation=schema_edge.relation,
                    strength=schema_edge.strength,
                    confidence=schema_edge.confidence,
                    shared_counterparties=schema_edge.shared_counterparties,
                    same_entity_likelihood=schema_edge.same_entity_likelihood,
                )
                g.add_edge(edge)

        _g = self._index.get_graph(cluster_id)
        logger.debug(
            "Populated cluster %r — %d nodes, %d edges",
            cluster_id,
            _g.node_count if _g else 0,
            _g.edge_count if _g else 0,
        )

    # ── Convenience reads ─────────────────────────────────────────────────────

    def get_cluster_meta(self, cluster_id: str) -> Optional[ClusterMeta]:
        """Return lightweight cluster summary without touching the graph."""
        return self._index.get_meta(cluster_id)

    def find_wallet_cluster(self, address: str) -> Optional[str]:
        """Return the cluster ID for *address*, or ``None`` if not indexed."""
        return self._index.find_cluster(address)

    def list_clusters(self) -> List[str]:
        """Return all known cluster IDs."""
        return self._index.list_clusters()

    @property
    def stats(self) -> Dict[str, int]:
        """Return a snapshot of store statistics."""
        return {
            "clusters": self._index.cluster_count,
            "nodes": self._index.total_nodes,
            "edges": self._index.total_edges,
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _add_wallet_to_cluster(
        self, cluster_id: str, address: str, chain: str, score: int, ts: str
    ) -> None:
        node = NodeMeta(
            address=address,
            chain=chain,
            score=score,
            confidence=50,
            last_active_at=ts,
        )
        self._index.add_node_to_cluster(cluster_id, node)

    def _touch_cluster(self, cluster_id: str, ts: str) -> None:
        """Recompute live confidence and update last_updated_at."""
        try:
            self.update_cluster(cluster_id, last_updated_at=ts)
        except KeyError:
            pass

    def _handle_cross_cluster_txn(
        self,
        src_cluster: str,
        dst_cluster: str,
        txn: TransactionRecord,
        ts: str,
    ) -> None:
        """Decide whether to merge two clusters or just add a cross-cluster edge."""
        MERGE_THRESHOLD = 70  # merge if combined confidence exceeds this

        src_conf = self._index.compute_confidence(src_cluster)
        dst_conf = self._index.compute_confidence(dst_cluster)
        combined = (src_conf + dst_conf) // 2

        if combined >= MERGE_THRESHOLD:
            # Merge smaller into larger
            src_g = self._index.get_graph(src_cluster)
            dst_g = self._index.get_graph(dst_cluster)
            src_size = src_g.node_count if src_g else 0
            dst_size = dst_g.node_count if dst_g else 0

            keep_id, discard_id = (src_cluster, dst_cluster) if src_size >= dst_size else (dst_cluster, src_cluster)
            self._index.merge_clusters(keep_id, discard_id)
            g = self._index.get_graph(keep_id)
            if g:
                g.add_edge(EdgeMeta(
                    source=txn.source,
                    target=txn.target,
                    relation=txn.relation,
                    strength=txn.strength,
                    confidence=combined,
                ))
            self._touch_cluster(keep_id, ts)
            logger.info("Merged cluster %r into %r (combined confidence=%d)", discard_id, keep_id, combined)
        else:
            # Add reinforcing edge without merging
            src_g = self._index.get_graph(src_cluster)
            if src_g:
                src_node = src_g.get_node(txn.source)
                if src_node:
                    src_node.update_activity(txn.volume_usd, ts)
            self._touch_cluster(src_cluster, ts)


def _derive_cluster_id(address: str, chain: str) -> str:
    import hashlib  # noqa: PLC0415
    return hashlib.sha1(f"{chain}:{address.lower()}".encode()).hexdigest()[:12]
