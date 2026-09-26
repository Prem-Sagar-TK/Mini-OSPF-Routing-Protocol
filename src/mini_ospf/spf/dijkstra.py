"""
Dijkstra's Shortest Path Algorithm with Deterministic Tie-Breaking and ECMP (RFC 2328 Section 16.1).
"""

import heapq
from dataclasses import dataclass, field

from mini_ospf.spf.graph import GraphEdge, TopologyGraph


@dataclass(slots=True)
class SPTResult:
    root: str
    distances: dict[str, int] = field(default_factory=dict)
    parents: dict[str, list[str]] = field(default_factory=dict)
    edges: dict[tuple[str, str], GraphEdge] = field(default_factory=dict)


def run_dijkstra_spt(graph: TopologyGraph, root: str) -> SPTResult:
    """
    Compute the Shortest Path Tree from 'root' to all reachable vertices.
    Supports Equal-Cost Multi-Path (ECMP) by maintaining multiple parents for equal-cost paths.
    Deterministic tie-breaking is enforced by comparing vertex string IDs in heap elements.
    """
    result = SPTResult(root=root)
    if root not in graph.vertices:
        return result

    distances: dict[str, float] = {v: float("inf") for v in graph.vertices}
    parents: dict[str, list[str]] = {v: [] for v in graph.vertices}
    edges: dict[tuple[str, str], GraphEdge] = {}

    distances[root] = 0
    # Min-heap elements: (cost, vertex_id)
    pq: list[tuple[int, str]] = [(0, root)]
    visited: set[str] = set()

    while pq:
        dist_u, u = heapq.heappop(pq)

        if u in visited:
            continue
        visited.add(u)

        for edge in graph.get_neighbors(u):
            v = edge.target
            new_dist = dist_u + edge.cost

            if new_dist < distances[v]:
                distances[v] = new_dist
                parents[v] = [u]
                edges[(u, v)] = edge
                heapq.heappush(pq, (new_dist, v))
            elif new_dist == distances[v] and u not in parents[v]:
                # Equal-Cost Multi-Path branch
                parents[v].append(u)
                edges[(u, v)] = edge

    result.distances = {k: int(v) for k, v in distances.items() if v != float("inf")}
    result.parents = {k: parents[k] for k in result.distances}
    result.edges = edges
    return result
