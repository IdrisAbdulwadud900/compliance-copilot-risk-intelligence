"""graph.py — Core in-process wallet relationship graph.

Design goals
────────────
* **O(1) node and edge access** — adjacency via ``dict`` keyed on address;
  edges stored as ``dict[(src, dst)]`` so both directions are indexed.
* **Thread-safe mutations** — a single ``threading.RLock`` guards all writes
  so callers can add transactions from concurrent request handlers without
  data corruption.
* **LRU-cached confidence scores** — per-node and per-cluster confidence are
  expensive to recompute; they are cached and invalidated only when the graph
  changes.
* **Memory-bounded** — ``max_nodes`` cap on a ``ClusterIndex``; evicts the
  least-recently-seen node when exceeded.
* **Zero hard dependencies** beyond the standard library — importable at cold
  start without touching the database or any external service.

Public surface
──────────────
    WalletGraph           — low-level labelled multi-graph
    ClusterIndex          — groups WalletGraphs into named clusters

The store layer (``cluster_store.py``) owns the singleton graph instance and
exposes the domain-level API (add_transaction, update_cluster,
query_relationships).
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import lru_cache
from typing import (
    Callable,
    Dict,
    FrozenSet,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
)


# ── Low-level types ───────────────────────────────────────────────────────────

Address = str
ClusterId = str
RelationLabel = str


@dataclass
class NodeMeta:
    """Metadata attached to a wallet node in the graph."""

    address: Address
    chain: str = "ethereum"
    score: int = 0
    risk_level: str = "low"
    # Rolling counters — updated by add_transaction
    txn_count: int = 0
    volume_usd: float = 0.0
    # Derived — recomputed by confidence scorer
    confidence: int = 0
    entity_likelihood: float = 0.0
    activity_band: str = "low"
    last_active_at: Optional[str] = None

    def update_activity(self, volume: float, ts: str) -> None:
        self.txn_count += 1
        self.volume_usd += volume
        self.last_active_at = ts
        # Re-bucket activity band
        if self.txn_count >= 250 or self.volume_usd >= 750_000:
            self.activity_band = "high"
        elif self.txn_count >= 50 or self.volume_usd >= 100_000:
            self.activity_band = "moderate"
        else:
            self.activity_band = "low"


@dataclass
class EdgeMeta:
    """Metadata attached to a directed edge (src → dst) in the graph."""

    source: Address
    target: Address
    relation: RelationLabel
    strength: float = 0.5
    confidence: int = 0
    shared_counterparties: int = 0
    same_entity_likelihood: float = 0.0
    # Each time a new transaction reinforces this edge, weight increases
    hit_count: int = 1

    def reinforce(self, strength_delta: float = 0.02) -> None:
        """Called when another transaction confirms this edge."""
        self.hit_count += 1
        self.strength = min(0.99, self.strength + strength_delta)
        self.confidence = min(100, self.confidence + 2)

    @property
    def key(self) -> Tuple[Address, Address]:
        return (self.source, self.target)


# ── WalletGraph ───────────────────────────────────────────────────────────────

class WalletGraph:
    """Labelled directed graph of wallet relationships.

    Internally maintained as two dicts:
        _nodes  : address → NodeMeta
        _edges  : (src, dst) → EdgeMeta

    Plus two adjacency sets for fast traversal:
        _out    : address → {target addresses}
        _in     : address → {source addresses}

    All public mutation methods are thread-safe.
    """

    def __init__(self, max_nodes: int = 10_000) -> None:
        self._max_nodes = max_nodes
        self._lock = threading.RLock()
        self._nodes: Dict[Address, NodeMeta] = {}
        self._edges: Dict[Tuple[Address, Address], EdgeMeta] = {}
        self._out: Dict[Address, Set[Address]] = defaultdict(set)
        self._in:  Dict[Address, Set[Address]] = defaultdict(set)
        # LRU order — used for eviction
        self._lru: deque[Address] = deque()
        # Invalidation counter — bumped on every structural change
        self._version: int = 0

    # ── Node API ──────────────────────────────────────────────────────────────

    def add_node(self, meta: NodeMeta) -> None:
        """Insert or replace a node. Evicts the oldest node if at capacity."""
        with self._lock:
            if meta.address not in self._nodes:
                if len(self._nodes) >= self._max_nodes:
                    self._evict_oldest()
                self._lru.append(meta.address)
            self._nodes[meta.address] = meta
            self._version += 1

    def get_node(self, address: Address) -> Optional[NodeMeta]:
        with self._lock:
            return self._nodes.get(address)

    def has_node(self, address: Address) -> bool:
        with self._lock:
            return address in self._nodes

    def update_node(self, address: Address, **kwargs: object) -> None:
        """Patch scalar fields on an existing node."""
        with self._lock:
            node = self._nodes.get(address)
            if node is None:
                raise KeyError(f"Node {address!r} not found")
            for k, v in kwargs.items():
                if not hasattr(node, k):
                    raise AttributeError(f"NodeMeta has no field {k!r}")
                setattr(node, k, v)
            self._version += 1

    def remove_node(self, address: Address) -> None:
        """Remove a node and all incident edges."""
        with self._lock:
            if address not in self._nodes:
                return
            # Remove all outgoing edges
            for target in list(self._out.get(address, set())):
                self._edges.pop((address, target), None)
                self._in[target].discard(address)
            self._out.pop(address, None)
            # Remove all incoming edges
            for source in list(self._in.get(address, set())):
                self._edges.pop((source, address), None)
                self._out[source].discard(address)
            self._in.pop(address, None)
            del self._nodes[address]
            try:
                self._lru.remove(address)
            except ValueError:
                pass
            self._version += 1

    # ── Edge API ──────────────────────────────────────────────────────────────

    def add_edge(self, meta: EdgeMeta) -> None:
        """Insert an edge. If the edge already exists, reinforce it instead."""
        with self._lock:
            key = meta.key
            existing = self._edges.get(key)
            if existing is not None:
                existing.reinforce()
                self._version += 1
                return
            # Ensure both endpoints exist (insert lightweight stubs if needed)
            for addr, chain in ((meta.source, "unknown"), (meta.target, "unknown")):
                if addr not in self._nodes:
                    self.add_node(NodeMeta(address=addr, chain=chain))
            self._edges[key] = meta
            self._out[meta.source].add(meta.target)
            self._in[meta.target].add(meta.source)
            self._version += 1

    def get_edge(self, source: Address, target: Address) -> Optional[EdgeMeta]:
        with self._lock:
            return self._edges.get((source, target))

    def has_edge(self, source: Address, target: Address) -> bool:
        with self._lock:
            return (source, target) in self._edges

    def remove_edge(self, source: Address, target: Address) -> None:
        with self._lock:
            if (source, target) not in self._edges:
                return
            del self._edges[(source, target)]
            self._out[source].discard(target)
            self._in[target].discard(source)
            self._version += 1

    # ── Traversal ─────────────────────────────────────────────────────────────

    def neighbors(self, address: Address) -> List[Address]:
        """Return all addresses reachable from *address* in one hop."""
        with self._lock:
            return list(self._out.get(address, set()))

    def predecessors(self, address: Address) -> List[Address]:
        """Return all addresses that have an edge *into* address."""
        with self._lock:
            return list(self._in.get(address, set()))

    def edges_from(self, address: Address) -> List[EdgeMeta]:
        """Return all outgoing edges from *address*."""
        with self._lock:
            return [self._edges[(address, t)] for t in self._out.get(address, set())]

    def edges_to(self, address: Address) -> List[EdgeMeta]:
        """Return all incoming edges to *address*."""
        with self._lock:
            return [self._edges[(s, address)] for s in self._in.get(address, set())]

    def bfs(
        self,
        start: Address,
        max_depth: int = 3,
        filter_fn: Optional[Callable[[EdgeMeta], bool]] = None,
    ) -> List[Address]:
        """Breadth-first traversal from *start*.

        Args:
            start:     Root address.
            max_depth: Maximum hops away from root.
            filter_fn: If provided, only traverse edges for which the callable
                       returns ``True``.

        Returns:
            List of reachable addresses (excluding the start address), in BFS
            order.
        """
        with self._lock:
            visited: Set[Address] = {start}
            queue: deque[Tuple[Address, int]] = deque([(start, 0)])
            result: List[Address] = []
            while queue:
                node, depth = queue.popleft()
                if depth >= max_depth:
                    continue
                for target in self._out.get(node, set()):
                    if target in visited:
                        continue
                    edge = self._edges.get((node, target))
                    if filter_fn is not None and edge is not None and not filter_fn(edge):
                        continue
                    visited.add(target)
                    result.append(target)
                    queue.append((target, depth + 1))
            return result

    def common_neighbors(self, a: Address, b: Address) -> List[Address]:
        """Return wallets directly connected to both *a* and *b*."""
        with self._lock:
            a_set = self._out.get(a, set()) | self._in.get(a, set())
            b_set = self._out.get(b, set()) | self._in.get(b, set())
            return list((a_set & b_set) - {a, b})

    def shortest_path(self, src: Address, dst: Address, max_depth: int = 6) -> List[Address]:
        """Return the shortest directed path from *src* to *dst* via BFS.

        Returns an empty list when no path exists within *max_depth* hops.
        """
        with self._lock:
            if src == dst:
                return [src]
            parent: Dict[Address, Optional[Address]] = {src: None}
            queue: deque[Address] = deque([src])
            depth_map: Dict[Address, int] = {src: 0}
            while queue:
                node = queue.popleft()
                if depth_map[node] >= max_depth:
                    continue
                for target in self._out.get(node, set()):
                    if target in parent:
                        continue
                    parent[target] = node
                    depth_map[target] = depth_map[node] + 1
                    if target == dst:
                        # Reconstruct path
                        path: List[Address] = []
                        cur: Optional[Address] = dst
                        while cur is not None:
                            path.append(cur)
                            cur = parent[cur]
                        return list(reversed(path))
                    queue.append(target)
            return []

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        with self._lock:
            return len(self._nodes)

    @property
    def edge_count(self) -> int:
        with self._lock:
            return len(self._edges)

    @property
    def version(self) -> int:
        """Monotonically increasing counter — incremented on every mutation.

        Consumers can store a snapshot of this value and compare later to
        check whether the graph has changed without re-reading all nodes.
        """
        with self._lock:
            return self._version

    def iter_nodes(self) -> Iterator[NodeMeta]:
        with self._lock:
            yield from list(self._nodes.values())

    def iter_edges(self) -> Iterator[EdgeMeta]:
        with self._lock:
            yield from list(self._edges.values())

    # ── Internals ─────────────────────────────────────────────────────────────

    def _evict_oldest(self) -> None:
        """Remove the least-recently-added node to stay within max_nodes."""
        while self._lru:
            oldest = self._lru.popleft()
            if oldest in self._nodes:
                # Remove without triggering version bump to avoid recursion
                del self._nodes[oldest]
                for target in list(self._out.pop(oldest, set())):
                    self._edges.pop((oldest, target), None)
                    self._in[target].discard(oldest)
                for source in list(self._in.pop(oldest, set())):
                    self._edges.pop((source, oldest), None)
                    self._out[source].discard(oldest)
                return


# ── ClusterIndex ──────────────────────────────────────────────────────────────

@dataclass
class ClusterMeta:
    """Summary data for a named cluster."""

    cluster_id: ClusterId
    root_address: Address
    confidence: int = 0
    cluster_score: int = 0
    cross_chain: bool = False
    heuristics: List[str] = field(default_factory=list)
    narrative: str = ""
    last_updated_at: Optional[str] = None
    refresh_suggested_after_sec: int = 60


class ClusterIndex:
    """Manages a collection of wallet graphs, one per cluster.

    Responsibilities
    ────────────────
    * Map wallet addresses to their cluster ID in O(1).
    * Provide a cluster-level graph for traversal and confidence queries.
    * Support merge: when two clusters share enough nodes they can be
      combined into one.
    * Provide a simple confidence scorer based on the graph topology that
      is LRU-cached at the (cluster_id, graph_version) level.

    Thread safety: the index lock serialises structural changes (add / merge /
    remove cluster); per-graph locks handle intra-cluster mutations.
    """

    def __init__(self, max_nodes_per_cluster: int = 10_000) -> None:
        self._max_nodes = max_nodes_per_cluster
        self._lock = threading.RLock()
        # cluster_id → WalletGraph
        self._graphs: Dict[ClusterId, WalletGraph] = {}
        # cluster_id → ClusterMeta
        self._meta: Dict[ClusterId, ClusterMeta] = {}
        # address → cluster_id (fast membership lookup)
        self._membership: Dict[Address, ClusterId] = {}

    # ── Cluster CRUD ──────────────────────────────────────────────────────────

    def create_cluster(self, cluster_id: ClusterId, root: NodeMeta, meta: ClusterMeta) -> WalletGraph:
        """Create an empty cluster rooted at *root* and return its graph."""
        with self._lock:
            if cluster_id in self._graphs:
                raise ValueError(f"Cluster {cluster_id!r} already exists")
            g = WalletGraph(max_nodes=self._max_nodes)
            g.add_node(root)
            self._graphs[cluster_id] = g
            self._meta[cluster_id] = meta
            self._membership[root.address] = cluster_id
            return g

    def get_graph(self, cluster_id: ClusterId) -> Optional[WalletGraph]:
        with self._lock:
            return self._graphs.get(cluster_id)

    def get_meta(self, cluster_id: ClusterId) -> Optional[ClusterMeta]:
        with self._lock:
            return self._meta.get(cluster_id)

    def update_meta(self, cluster_id: ClusterId, **kwargs: object) -> None:
        with self._lock:
            meta = self._meta.get(cluster_id)
            if meta is None:
                raise KeyError(f"Cluster {cluster_id!r} not found")
            for k, v in kwargs.items():
                if not hasattr(meta, k):
                    raise AttributeError(f"ClusterMeta has no field {k!r}")
                setattr(meta, k, v)

    def delete_cluster(self, cluster_id: ClusterId) -> None:
        with self._lock:
            g = self._graphs.pop(cluster_id, None)
            if g is None:
                return
            for node in g.iter_nodes():
                self._membership.pop(node.address, None)
            self._meta.pop(cluster_id, None)

    def list_clusters(self) -> List[ClusterId]:
        with self._lock:
            return list(self._graphs.keys())

    # ── Node ↔ Cluster ────────────────────────────────────────────────────────

    def add_node_to_cluster(self, cluster_id: ClusterId, node: NodeMeta) -> None:
        with self._lock:
            g = self._graphs.get(cluster_id)
            if g is None:
                raise KeyError(f"Cluster {cluster_id!r} not found")
            old_cluster = self._membership.get(node.address)
            if old_cluster and old_cluster != cluster_id:
                # Move membership
                self._membership[node.address] = cluster_id
            elif not old_cluster:
                self._membership[node.address] = cluster_id
            g.add_node(node)

    def find_cluster(self, address: Address) -> Optional[ClusterId]:
        """Return the cluster ID that contains *address*, or ``None``."""
        with self._lock:
            return self._membership.get(address)

    # ── Merge ─────────────────────────────────────────────────────────────────

    def merge_clusters(self, keep_id: ClusterId, discard_id: ClusterId) -> None:
        """Absorb *discard_id* into *keep_id*.

        All nodes and edges from the discarded cluster graph are copied into
        the kept cluster graph.  Membership pointers are updated.
        """
        with self._lock:
            keep_graph = self._graphs.get(keep_id)
            discard_graph = self._graphs.get(discard_id)
            if keep_graph is None:
                raise KeyError(f"Cluster {keep_id!r} not found")
            if discard_graph is None:
                raise KeyError(f"Cluster {discard_id!r} not found")

            for node in discard_graph.iter_nodes():
                keep_graph.add_node(node)
                self._membership[node.address] = keep_id

            for edge in discard_graph.iter_edges():
                keep_graph.add_edge(edge)

            self._graphs.pop(discard_id)
            self._meta.pop(discard_id, None)

    # ── Confidence scoring ────────────────────────────────────────────────────

    def compute_confidence(self, cluster_id: ClusterId) -> int:
        """Return a [0–100] confidence score for the cluster.

        The result is cached at the (cluster_id, graph_version) key so
        repeated calls on an unchanged graph are O(1).
        """
        g = self._graphs.get(cluster_id)
        if g is None:
            return 0
        return _cached_confidence(cluster_id, g.version, g)

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def cluster_count(self) -> int:
        with self._lock:
            return len(self._graphs)

    @property
    def total_nodes(self) -> int:
        with self._lock:
            return sum(g.node_count for g in self._graphs.values())

    @property
    def total_edges(self) -> int:
        with self._lock:
            return sum(g.edge_count for g in self._graphs.values())


# ── Confidence computation (cached) ──────────────────────────────────────────

def _cached_confidence(cluster_id: ClusterId, version: int, g: WalletGraph) -> int:
    """Cached topology-based confidence scorer.

    The ``version`` arg acts as the cache-buster; the LRU key is
    ``(cluster_id, version)`` so stale entries are automatically bypassed
    when the graph changes.  The ``g`` argument is excluded from hashing
    (it's a mutable object) and is passed only to read topology.
    """
    return _topology_confidence(cluster_id, version, g)


@lru_cache(maxsize=512)
def _topology_confidence(cluster_id: ClusterId, version: int, g: WalletGraph) -> int:  # noqa: ARG001
    """Pure topology-based confidence — called only on cache miss."""
    nodes = list(g.iter_nodes())
    edges = list(g.iter_edges())

    if not nodes:
        return 0

    # Average per-node confidence (excluding root which is always 100)
    non_root_confs = [n.confidence for n in nodes if not getattr(n, "is_root", False) and n.confidence > 0]
    node_avg = sum(non_root_confs) / len(non_root_confs) if non_root_confs else 0.0

    # Average edge confidence
    edge_avg = sum(e.confidence for e in edges) / len(edges) if edges else 0.0

    # Structural bonus: denser graph = more corroborating evidence
    density = len(edges) / max(1, len(nodes) * (len(nodes) - 1))
    density_bonus = min(10.0, density * 50.0)

    # Edge reinforcement bonus
    reinforce_bonus = min(5.0, sum(e.hit_count - 1 for e in edges) * 0.5)

    score = 0.45 * node_avg + 0.35 * edge_avg + density_bonus + reinforce_bonus
    return int(max(0.0, min(100.0, round(score))))
