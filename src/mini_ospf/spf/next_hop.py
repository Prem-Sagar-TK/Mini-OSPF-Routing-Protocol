"""
Next-Hop Resolution and Multi-Path Route Candidate Generation (RFC 2328 Section 16.1.1).
"""

from dataclasses import dataclass, field

from mini_ospf.routing.next_hop import NextHop
from mini_ospf.routing.route import Route, RouteType
from mini_ospf.spf.dijkstra import SPTResult
from mini_ospf.spf.graph import TopologyGraph


@dataclass(slots=True)
class RouteCandidate:
    prefix: str
    prefix_length: int
    metric: int
    next_hops: list[NextHop] = field(default_factory=list)
    route_type: RouteType = RouteType.INTRA_AREA


def _mask_to_prefix_len(mask_str: str) -> int:
    try:
        octets = [int(x) for x in mask_str.split(".")]
        binary_str = "".join(f"{octet:08b}" for octet in octets)
        return binary_str.count("1")
    except Exception:
        return 24


def compute_next_hops_for_node(
    node: str,
    spt: SPTResult,
    direct_neighbors: dict[str, str],  # neighbor_router_id -> neighbor_ip or interface_name
) -> list[NextHop]:
    """
    Recursively/iteratively trace paths back from 'node' to 'root' to find the immediate next-hops.
    Supports ECMP branches.
    """
    root = spt.root
    if node == root:
        return []

    # If node is a direct child of root
    if root in spt.parents.get(node, []):
        edge = spt.edges.get((root, node))
        ip = edge.link_data if edge and edge.link_data else direct_neighbors.get(node, "")
        return [NextHop(ip_address=ip, interface_name=node)]

    # Multi-hop: trace all paths back
    next_hops: set[NextHop] = set()
    visited: set[str] = set()

    def _find_hops(cur: str) -> None:
        if cur in visited:
            return
        visited.add(cur)

        for parent in spt.parents.get(cur, []):
            if parent == root:
                edge = spt.edges.get((root, cur))
                ip = edge.link_data if edge and edge.link_data else direct_neighbors.get(cur, "")
                next_hops.add(NextHop(ip_address=ip, interface_name=cur))
            else:
                _find_hops(parent)

    _find_hops(node)
    return sorted(next_hops, key=lambda nh: (nh.ip_address, nh.interface_name))


def generate_route_candidates(
    graph: TopologyGraph,
    spt: SPTResult,
    direct_neighbors: dict[str, str] | None = None,
) -> list[Route]:
    """
    Convert Shortest Path Tree (SPT) and attached networks into IP Route candidates for the RIB.
    """
    if direct_neighbors is None:
        direct_neighbors = {}

    routes: list[Route] = []
    root = spt.root

    # 1. Router host routes (/32 router-id)
    for node, dist in spt.distances.items():
        if node == root or node.startswith("NET_"):
            continue

        nhops = compute_next_hops_for_node(node, spt, direct_neighbors)
        routes.append(
            Route(
                prefix=node,
                prefix_length=32,
                metric=dist,
                next_hops=nhops,
                route_type=RouteType.INTRA_AREA,
            )
        )

    # 2. Stub networks attached to reachable routers
    for rtr_id, stubs in graph.stub_networks.items():
        if rtr_id not in spt.distances:
            continue

        rtr_dist = spt.distances[rtr_id]
        nhops = compute_next_hops_for_node(rtr_id, spt, direct_neighbors)

        for net_ip, net_mask, stub_cost in stubs:
            prefix_len = _mask_to_prefix_len(net_mask)
            routes.append(
                Route(
                    prefix=net_ip,
                    prefix_length=prefix_len,
                    metric=rtr_dist + stub_cost,
                    next_hops=nhops,
                    route_type=RouteType.INTRA_AREA,
                )
            )

    return routes
