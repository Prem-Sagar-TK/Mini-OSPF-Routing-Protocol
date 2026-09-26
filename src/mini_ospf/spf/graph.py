"""
Topology Graph Construction and Bidirectional Link Verification (RFC 2328 Section 16.1).
"""

from dataclasses import dataclass, field

from mini_ospf.lsdb.database import LinkStateDatabase
from mini_ospf.protocol.constants import RouterLinkType


@dataclass(slots=True)
class GraphEdge:
    source: str
    target: str
    cost: int
    link_type: RouterLinkType
    link_data: str = ""  # IP address or subnet mask


@dataclass(slots=True)
class TopologyGraph:
    vertices: set[str] = field(default_factory=set)
    adj: dict[str, list[GraphEdge]] = field(default_factory=dict)
    stub_networks: dict[str, list[tuple[str, str, int]]] = field(default_factory=dict)
    # router_id -> list of (subnet_ip, subnet_mask, cost)

    def add_vertex(self, v: str) -> None:
        self.vertices.add(v)
        if v not in self.adj:
            self.adj[v] = []

    def add_edge(self, edge: GraphEdge) -> None:
        self.add_vertex(edge.source)
        self.add_vertex(edge.target)
        self.adj[edge.source].append(edge)

    def get_neighbors(self, u: str) -> list[GraphEdge]:
        return self.adj.get(u, [])


def build_topology_graph(lsdb: LinkStateDatabase) -> TopologyGraph:
    """
    Build directed topology graph from active Router-LSAs and Network-LSAs in the LSDB,
    strictly verifying bidirectional link connectivity (RFC 2328 Section 16.1).
    """
    graph = TopologyGraph()
    router_lsas = {lsa.header.advertising_router: lsa for lsa in lsdb.get_router_lsas()}
    network_lsas = {lsa.header.link_state_id: lsa for lsa in lsdb.get_network_lsas()}

    # Register all router nodes
    for rtr_id in router_lsas:
        graph.add_vertex(rtr_id)

    # Process Router-LSAs
    for rtr_id, r_lsa in router_lsas.items():
        stubs: list[tuple[str, str, int]] = []
        for link in r_lsa.links:
            if link.link_type == RouterLinkType.POINT_TO_POINT:
                neigh_id = link.link_id
                # Bidirectional check: neigh_id must have a Router-LSA with a P2P link back to rtr_id
                neigh_lsa = router_lsas.get(neigh_id)
                if neigh_lsa is not None:
                    has_reverse = any(
                        nl.link_type == RouterLinkType.POINT_TO_POINT and nl.link_id == rtr_id
                        for nl in neigh_lsa.links
                    )
                    if has_reverse:
                        graph.add_edge(
                            GraphEdge(
                                source=rtr_id,
                                target=neigh_id,
                                cost=link.metric,
                                link_type=RouterLinkType.POINT_TO_POINT,
                                link_data=link.link_data,
                            )
                        )

            elif link.link_type == RouterLinkType.TRANSIT_NETWORK:
                net_id = link.link_id  # IP of Designated Router
                net_lsa = network_lsas.get(net_id)
                if net_lsa is not None and rtr_id in net_lsa.attached_routers:
                    # Valid transit link to pseudo-node net_id
                    graph.add_edge(
                        GraphEdge(
                            source=rtr_id,
                            target=f"NET_{net_id}",
                            cost=link.metric,
                            link_type=RouterLinkType.TRANSIT_NETWORK,
                            link_data=link.link_data,
                        )
                    )
                    # And pseudo-node back to router with cost 0
                    graph.add_edge(
                        GraphEdge(
                            source=f"NET_{net_id}",
                            target=rtr_id,
                            cost=0,
                            link_type=RouterLinkType.TRANSIT_NETWORK,
                            link_data=net_lsa.network_mask,
                        )
                    )

            elif link.link_type == RouterLinkType.STUB_NETWORK:
                # Stub network: link_id is IP prefix, link_data is subnet mask
                stubs.append((link.link_id, link.link_data, link.metric))

        if stubs:
            graph.stub_networks[rtr_id] = stubs

    return graph
