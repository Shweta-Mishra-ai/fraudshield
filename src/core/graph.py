"""
Graph Engine — detects fraud rings using bipartite user–entity graphs.
Connects Users ↔ Devices ↔ IPs ↔ Merchants.
Shared resources between many users = classic fraud ring pattern.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Set

import networkx as nx

logger = logging.getLogger(__name__)


class FraudGraphEngine:
    """
    Builds and queries a fraud relationship graph.

    Nodes:  user:<id>, device:<id>, ip:<ip>, merchant:<id>
    Edges:  weighted by transaction amount (higher spend = stronger edge)
    """

    # Thresholds for ring detection
    RING_DEVICE_MIN_USERS = 3
    RING_IP_MIN_USERS     = 5

    def __init__(self) -> None:
        self._graph: nx.Graph = nx.Graph()
        # Reverse index: entity → set of users (faster lookups than graph traversal)
        self._device_users:   Dict[str, Set[str]] = defaultdict(set)
        self._ip_users:       Dict[str, Set[str]] = defaultdict(set)
        self._merchant_users: Dict[str, Set[str]] = defaultdict(set)

    # ──────────────────────────────────────────────────────────────────────
    # Graph construction
    # ──────────────────────────────────────────────────────────────────────

    def add_transaction(self, tx) -> None:  # tx: Transaction (avoid circular import)
        """
        Add a transaction's entities and relationships to the graph.
        Call this AFTER scoring to avoid data leakage.
        """
        u_node = f"user:{tx.user_id}"
        d_node = f"device:{tx.device_id}"
        i_node = f"ip:{tx.ip_address}"
        m_node = f"merchant:{tx.merchant_id}"

        # ── Nodes ──────────────────────────────────────────────────────
        self._graph.add_node(u_node, type="user",     label=tx.user_id)
        self._graph.add_node(d_node, type="device",   label=tx.device_id)
        self._graph.add_node(i_node, type="ip",       label=tx.ip_address)
        self._graph.add_node(m_node, type="merchant", label=tx.merchant_id)

        # ── Edges (accumulate weight) ───────────────────────────────────
        for a, b in [(u_node, d_node), (u_node, i_node), (u_node, m_node),
                     (d_node, i_node)]:
            if self._graph.has_edge(a, b):
                self._graph[a][b]["weight"] += tx.amount
                self._graph[a][b]["count"]  += 1
            else:
                self._graph.add_edge(a, b, weight=tx.amount, count=1)

        # ── Reverse indices ─────────────────────────────────────────────
        self._device_users[tx.device_id].add(tx.user_id)
        self._ip_users[tx.ip_address].add(tx.user_id)
        self._merchant_users[tx.merchant_id].add(tx.user_id)

    # ──────────────────────────────────────────────────────────────────────
    # Scoring
    # ──────────────────────────────────────────────────────────────────────

    def user_ring_score(self, user_id: str, device_id: str, ip_address: str) -> float:
        """
        Returns a fraud-ring risk score 0–1 for this user/device/ip combo.
        High score = this device or IP is shared with many OTHER users.
        """
        device_users = self._device_users.get(device_id, set())
        ip_users     = self._ip_users.get(ip_address, set())

        other_device_users = len(device_users - {user_id})
        other_ip_users     = len(ip_users - {user_id})

        # Normalize: 9+ other users on same device → score 1.0
        device_score = min(other_device_users / 9.0, 1.0) if other_device_users > 0 else 0.0
        # Normalize: 14+ other users on same IP → score 1.0
        ip_score     = min(other_ip_users     / 14.0, 1.0) if other_ip_users > 0 else 0.0

        return round(max(device_score, ip_score), 4)

    # ──────────────────────────────────────────────────────────────────────
    # Ring detection (batch — run periodically)
    # ──────────────────────────────────────────────────────────────────────

    def detect_rings(self) -> List[Dict]:
        """
        Scan the graph for fraud ring candidates.
        Returns list of ring dicts with risk score + member users.
        """
        rings: List[Dict] = []

        # ── Device rings ────────────────────────────────────────────────
        for device, users in self._device_users.items():
            if len(users) >= self.RING_DEVICE_MIN_USERS:
                rings.append({
                    "type":       "shared_device",
                    "entity":     device,
                    "users":      list(users),
                    "user_count": len(users),
                    "risk_score": min(len(users) / 10.0, 1.0),
                    "reason":     f"Device shared by {len(users)} users",
                })

        # ── IP rings ────────────────────────────────────────────────────
        for ip, users in self._ip_users.items():
            if len(users) >= self.RING_IP_MIN_USERS:
                rings.append({
                    "type":       "shared_ip",
                    "entity":     ip,
                    "users":      list(users),
                    "user_count": len(users),
                    "risk_score": min(len(users) / 15.0, 1.0),
                    "reason":     f"IP used by {len(users)} different users",
                })

        # Sort by risk descending
        rings.sort(key=lambda r: r["risk_score"], reverse=True)
        return rings

    # ──────────────────────────────────────────────────────────────────────
    # Visualization export
    # ──────────────────────────────────────────────────────────────────────

    def get_subgraph_for_user(self, user_id: str, depth: int = 2) -> Dict:
        """
        Return a serializable sub-graph centred on a user up to `depth` hops.
        Used by the dashboard for network visualization.
        """
        u_node = f"user:{user_id}"
        if u_node not in self._graph:
            return {"nodes": [], "edges": []}

        # BFS to depth
        nodes_in_sub: Set[str] = {u_node}
        frontier = {u_node}
        for _ in range(depth):
            next_frontier: Set[str] = set()
            for n in frontier:
                for nb in self._graph.neighbors(n):
                    if nb not in nodes_in_sub:
                        nodes_in_sub.add(nb)
                        next_frontier.add(nb)
            frontier = next_frontier

        sub = self._graph.subgraph(nodes_in_sub)
        color_map = {"user": "#4F8EF7", "device": "#F7A24F", "ip": "#F74F4F", "merchant": "#4FF79A"}

        nodes = [
            {
                "id":    n,
                "label": sub.nodes[n].get("label", n),
                "type":  sub.nodes[n].get("type", "unknown"),
                "color": color_map.get(sub.nodes[n].get("type", ""), "#ccc"),
            }
            for n in sub.nodes()
        ]
        edges = [
            {
                "source": e[0],
                "target": e[1],
                "weight": round(e[2].get("weight", 1), 2),
                "count":  e[2].get("count", 1),
            }
            for e in sub.edges(data=True)
        ]
        return {"nodes": nodes, "edges": edges}

    def get_stats(self) -> Dict:
        user_nodes = [n for n, d in self._graph.nodes(data=True) if d.get("type") == "user"]
        return {
            "total_nodes":          self._graph.number_of_nodes(),
            "total_edges":          self._graph.number_of_edges(),
            "unique_users":         len(user_nodes),
            "unique_devices":       len(self._device_users),
            "unique_ips":           len(self._ip_users),
            "connected_components": nx.number_connected_components(self._graph),
        }
