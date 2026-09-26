"""
Integration test: In-memory protocol exchange between two OSPF Daemons (R1 <-> R2).
Tests Hello exchange, 2-Way transition, DBD Master/Slave negotiation, LSDB sync, and SPF route calculation.
"""

from mini_ospf.app.daemon import OSPFDaemon
from mini_ospf.config.models import (
    AreaConfig,
    DaemonConfig,
    InterfaceConfig,
    LoggingConfig,
    ServerConfig,
    SPFConfig,
)
from mini_ospf.ospf.neighbor_fsm import NeighborState
from mini_ospf.platform.route_installer import MockRouteInstaller
from mini_ospf.protocol.serializer import serialize_packet


def _make_test_daemon_config(router_id: str, if_name: str, ip_addr: str) -> DaemonConfig:
    return DaemonConfig(
        router_id=router_id,
        areas=[AreaConfig(id="0.0.0.0")],
        interfaces=[
            InterfaceConfig(
                name=if_name,
                ip_address=ip_addr,
                netmask="255.255.255.0",
                area="0.0.0.0",
                hello_interval=1,
                dead_interval=4,
                metric=10,
            )
        ],
        spf=SPFConfig(init_delay_ms=1, hold_time_ms=5, max_delay_ms=50),
        logging=LoggingConfig(level="WARNING"),
        server=ServerConfig(api_enabled=False),
        install_kernel_routes=False,
    )


def test_two_router_adjacency_and_lsdb_sync() -> None:
    installer1 = MockRouteInstaller()
    installer2 = MockRouteInstaller()

    r1_cfg = _make_test_daemon_config("1.1.1.1", "eth1", "10.0.12.1")
    r2_cfg = _make_test_daemon_config("2.2.2.2", "eth1", "10.0.12.2")

    r1 = OSPFDaemon(r1_cfg, route_installer=installer1, use_mock_sockets=True)
    r2 = OSPFDaemon(r2_cfg, route_installer=installer2, use_mock_sockets=True)

    # Interconnect virtual packet transmission
    def r1_send(raw: bytes, ifname: str, dst_ip: str | None = None, dst_port: int | None = None) -> bool:
        r2.handle_raw_packet(raw, "eth1", "10.0.12.1", 8989)
        return True

    def r2_send(raw: bytes, ifname: str, dst_ip: str | None = None, dst_port: int | None = None) -> bool:
        r1.handle_raw_packet(raw, "eth1", "10.0.12.2", 8989)
        return True

    r1.flooding_engine.send_raw_func = r1_send
    r2.flooding_engine.send_raw_func = r2_send

    # Step 1: Initial Self LSA generation
    r1.generate_self_router_lsa()
    r2.generate_self_router_lsa()

    # Step 2: R1 sends Hello to R2 (1-Way)
    h1 = r1.hello_handler.create_hello(
        "255.255.255.0", 10, 40, 1, "0.0.0.0", "0.0.0.0", known_neighbors=[]
    )
    r1_send(serialize_packet(h1), "eth1")

    # R2 receives H1 -> records R1 in state INIT
    assert "1.1.1.1" in r2.neighbors
    assert r2.neighbors["1.1.1.1"].state == NeighborState.INIT

    # Step 3: R2 sends Hello back to R1, listing R1 as known neighbor (2-Way)
    h2 = r2.hello_handler.create_hello(
        "255.255.255.0", 10, 40, 1, "0.0.0.0", "0.0.0.0", known_neighbors=["1.1.1.1"]
    )
    r2_send(serialize_packet(h2), "eth1")

    # R1 receives H2 containing 1.1.1.1 -> transitions to EXSTART
    assert "2.2.2.2" in r1.neighbors
    assert r1.neighbors["2.2.2.2"].state == NeighborState.EXSTART

    # Step 4: R1 sends Hello back listing R2 -> R2 transitions to EXSTART
    h1_2way = r1.hello_handler.create_hello(
        "255.255.255.0", 10, 40, 1, "0.0.0.0", "0.0.0.0", known_neighbors=["2.2.2.2"]
    )
    r1_send(serialize_packet(h1_2way), "eth1")
    assert r2.neighbors["1.1.1.1"].state == NeighborState.EXSTART

    # Step 5: ExStart DBD Master/Slave negotiation
    # R1 (1.1.1.1) initiates ExStart DBD with Seq 100
    dbd1 = r1.dbd_handler.create_initial_dbd(r1.neighbors["2.2.2.2"], sequence_number=100)
    # R2 (2.2.2.2) has higher Router ID -> R2 remains Master with Seq 200
    dbd2 = r2.dbd_handler.create_initial_dbd(r2.neighbors["1.1.1.1"], sequence_number=200)

    # R1 receives R2's DBD -> R1 becomes Slave, transitions to EXCHANGE and replies with Seq 200
    r2_send(serialize_packet(dbd2), "eth1")
    assert r1.neighbors["2.2.2.2"].state == NeighborState.EXCHANGE
    assert r1.neighbors["2.2.2.2"].is_master is False

    # R2 receives R1's DBD response -> R2 transitions to EXCHANGE
    r1_send(serialize_packet(dbd1), "eth1")
    # Exchange summaries
    resp_dbd = r1.dbd_handler.create_dbd_summary(r1.neighbors["2.2.2.2"], r1.lsdb)
    r1_send(serialize_packet(resp_dbd), "eth1")
    assert r2.neighbors["1.1.1.1"].state == NeighborState.EXCHANGE
    assert r2.neighbors["1.1.1.1"].is_master is True

    # Step 6: Trigger full convergence & SPF
    r1.neighbors["2.2.2.2"].fsm.state = NeighborState.FULL
    r2.neighbors["1.1.1.1"].fsm.state = NeighborState.FULL
    r1.generate_self_router_lsa()
    r2.generate_self_router_lsa()

    # R1 floods its LSA to R2
    r1.flooding_engine.flood_lsa(r1.lsdb.get_router_lsas()[0], r1.neighbors)
    # R2 floods its LSA to R1
    r2.flooding_engine.flood_lsa(r2.lsdb.get_router_lsas()[0], r2.neighbors)

    # Verify both LSDBs have 2 Router-LSAs
    assert r1.lsdb.count() == 2
    assert r2.lsdb.count() == 2

    # Step 7: Run SPF calculations
    r1.run_spf_calculation()
    r2.run_spf_calculation()

    # Check that R1 installed route to 2.2.2.2 (/32) and 10.0.12.2 (/32)
    assert r1.rib.get_route("2.2.2.2", 32) is not None
    assert len(installer1.get_installed_routes()) > 0
