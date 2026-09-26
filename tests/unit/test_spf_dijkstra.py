"""
Unit tests for Dijkstra SPT, Bidirectional Link verification, and ECMP next-hop calculation.
"""

from mini_ospf.lsdb.database import LinkStateDatabase
from mini_ospf.protocol.constants import LSAType, RouterLinkType
from mini_ospf.protocol.packet import LSAHeader, RouterLink, RouterLSA
from mini_ospf.spf.dijkstra import run_dijkstra_spt
from mini_ospf.spf.graph import GraphEdge, TopologyGraph, build_topology_graph
from mini_ospf.spf.next_hop import generate_route_candidates


def _make_router_lsa(router_id: str, links: list[tuple[str, str, RouterLinkType, int]]) -> RouterLSA:
    r_links = [
        RouterLink(link_id=lid, link_data=ldata, link_type=ltype, metric=cost)
        for lid, ldata, ltype, cost in links
    ]
    hdr = LSAHeader(
        ls_type=LSAType.ROUTER,
        link_state_id=router_id,
        advertising_router=router_id,
        ls_sequence_number=1,
    )
    return RouterLSA(header=hdr, num_links=len(r_links), links=r_links)


def test_dijkstra_diamond_topology() -> None:
    # Topology:
    #   R1 -(10)- R2 -(10)- R4
    #   R1 -(30)- R3 -(10)- R4
    # Shortest path to R4 should be via R2 (cost 20) vs via R3 (cost 40).
    graph = TopologyGraph()
    graph.add_edge(GraphEdge("1.1.1.1", "2.2.2.2", 10, RouterLinkType.POINT_TO_POINT, "10.0.12.2"))
    graph.add_edge(GraphEdge("1.1.1.1", "3.3.3.3", 30, RouterLinkType.POINT_TO_POINT, "10.0.13.3"))
    graph.add_edge(GraphEdge("2.2.2.2", "4.4.4.4", 10, RouterLinkType.POINT_TO_POINT, "10.0.24.4"))
    graph.add_edge(GraphEdge("3.3.3.3", "4.4.4.4", 10, RouterLinkType.POINT_TO_POINT, "10.0.34.4"))

    spt = run_dijkstra_spt(graph, "1.1.1.1")

    assert spt.distances["1.1.1.1"] == 0
    assert spt.distances["2.2.2.2"] == 10
    assert spt.distances["3.3.3.3"] == 30
    assert spt.distances["4.4.4.4"] == 20  # via R2
    assert spt.parents["4.4.4.4"] == ["2.2.2.2"]


def test_dijkstra_ecmp() -> None:
    # Equal cost:
    #   R1 -(10)- R2 -(10)- R4  (cost 20)
    #   R1 -(10)- R3 -(10)- R4  (cost 20)
    graph = TopologyGraph()
    graph.add_edge(GraphEdge("1.1.1.1", "2.2.2.2", 10, RouterLinkType.POINT_TO_POINT, "10.0.12.2"))
    graph.add_edge(GraphEdge("1.1.1.1", "3.3.3.3", 10, RouterLinkType.POINT_TO_POINT, "10.0.13.3"))
    graph.add_edge(GraphEdge("2.2.2.2", "4.4.4.4", 10, RouterLinkType.POINT_TO_POINT, "10.0.24.4"))
    graph.add_edge(GraphEdge("3.3.3.3", "4.4.4.4", 10, RouterLinkType.POINT_TO_POINT, "10.0.34.4"))

    spt = run_dijkstra_spt(graph, "1.1.1.1")
    assert spt.distances["4.4.4.4"] == 20
    # Both R2 and R3 should be parents
    assert set(spt.parents["4.4.4.4"]) == {"2.2.2.2", "3.3.3.3"}

    # Route candidates should show ECMP next hops
    direct_map = {"2.2.2.2": "10.0.12.2", "3.3.3.3": "10.0.13.3"}
    candidates = generate_route_candidates(graph, spt, direct_map)
    r4_route = next(r for r in candidates if r.prefix == "4.4.4.4")
    assert len(r4_route.next_hops) == 2


def test_bidirectional_link_verification() -> None:
    """RFC 2328: If R1 advertises link to R2, but R2 does not advertise link to R1, drop the edge."""
    lsdb = LinkStateDatabase()

    # R1 advertises link to R2
    r1_lsa = _make_router_lsa(
        "1.1.1.1", [("2.2.2.2", "10.0.12.1", RouterLinkType.POINT_TO_POINT, 10)]
    )
    # R2 advertises only a link to R3 (NOT to R1)
    r2_lsa = _make_router_lsa(
        "2.2.2.2", [("3.3.3.3", "10.0.23.2", RouterLinkType.POINT_TO_POINT, 10)]
    )

    lsdb.install(r1_lsa)
    lsdb.install(r2_lsa)

    graph = build_topology_graph(lsdb)
    # R1 should have NO neighbors because R2 didn't confirm the link back
    assert len(graph.get_neighbors("1.1.1.1")) == 0
