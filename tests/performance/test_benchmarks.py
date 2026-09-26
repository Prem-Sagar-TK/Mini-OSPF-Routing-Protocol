"""
Performance and Scalability Benchmarks for SPF Dijkstra, Packet Parsing, and LSDB operations.
"""

import time

from mini_ospf.lsdb.database import LinkStateDatabase
from mini_ospf.platform.route_installer import MockRouteInstaller
from mini_ospf.protocol.constants import LSAType, RouterLinkType
from mini_ospf.protocol.packet import (
    HelloPacket,
    LSAHeader,
    OSPFHeader,
    RouterLSA,
)
from mini_ospf.protocol.parser import parse_packet
from mini_ospf.protocol.serializer import serialize_packet
from mini_ospf.routing.route import Route
from mini_ospf.spf.dijkstra import run_dijkstra_spt
from mini_ospf.spf.graph import GraphEdge, TopologyGraph


def _generate_synthetic_graph(num_nodes: int, degree: int = 4) -> TopologyGraph:
    """Generate a synthetic connected mesh/grid topology graph with num_nodes."""
    graph = TopologyGraph()
    for i in range(num_nodes):
        node = f"10.0.{i // 256}.{i % 256}"
        graph.add_vertex(node)

    nodes = list(graph.vertices)
    for i, u in enumerate(nodes):
        for d in range(1, degree + 1):
            target_idx = (i + d) % num_nodes
            v = nodes[target_idx]
            graph.add_edge(GraphEdge(u, v, cost=10, link_type=RouterLinkType.POINT_TO_POINT))
            graph.add_edge(GraphEdge(v, u, cost=10, link_type=RouterLinkType.POINT_TO_POINT))

    return graph


def test_benchmark_spf_scaling() -> None:
    """Benchmark SPF Dijkstra algorithm across 10, 100, 1,000, and 10,000 node topologies."""
    sizes = [10, 100, 1000, 10000]
    results: dict[int, float] = {}

    for n in sizes:
        graph = _generate_synthetic_graph(n, degree=4)
        root = list(graph.vertices)[0]

        start = time.perf_counter()
        spt = run_dijkstra_spt(graph, root)
        duration_ms = (time.perf_counter() - start) * 1000.0
        results[n] = duration_ms

        assert len(spt.distances) == n
        print(f"[BENCHMARK] Dijkstra SPF ({n:>5} nodes, {n*4:>5} edges): {duration_ms:>8.3f} ms")


def test_benchmark_packet_parser_throughput() -> None:
    """Measure packet serialization and parsing throughput in packets/sec."""
    pkt = HelloPacket(
        header=OSPFHeader(router_id="1.1.1.1"),
        network_mask="255.255.255.0",
        neighbors=["2.2.2.2", "3.3.3.3", "4.4.4.4"],
    )
    raw = serialize_packet(pkt)
    iterations = 5000

    start = time.perf_counter()
    for _ in range(iterations):
        _ = parse_packet(raw)
    duration = time.perf_counter() - start

    rate = iterations / duration
    print(f"[BENCHMARK] Packet Parser: {iterations} packets in {duration:.3f}s ({rate:,.1f} packets/sec)")
    assert rate > 1000.0


def test_benchmark_lsdb_throughput() -> None:
    """Measure LSDB insertion throughput."""
    lsdb = LinkStateDatabase()
    count = 2000

    lsas = []
    for i in range(count):
        rtr = f"10.0.{i // 256}.{i % 256}"
        hdr = LSAHeader(
            ls_type=LSAType.ROUTER,
            link_state_id=rtr,
            advertising_router=rtr,
            ls_sequence_number=1,
        )
        lsas.append(RouterLSA(header=hdr))

    start = time.perf_counter()
    for lsa in lsas:
        lsdb.install(lsa)
    duration = time.perf_counter() - start

    rate = count / duration
    print(f"[BENCHMARK] LSDB Insert: {count} LSAs in {duration:.3f}s ({rate:,.1f} LSAs/sec)")
    assert lsdb.count() == count


def test_benchmark_route_installer_throughput() -> None:
    installer = MockRouteInstaller()
    count = 5000
    routes = [Route(prefix=f"10.{i // 256}.{i % 256}.0", prefix_length=24, metric=10) for i in range(count)]

    start = time.perf_counter()
    for r in routes:
        installer.install_route(r)
    duration = time.perf_counter() - start

    rate = count / duration
    print(f"[BENCHMARK] Route Installer: {count} routes in {duration:.3f}s ({rate:,.1f} routes/sec)")
    assert len(installer.get_installed_routes()) == count
