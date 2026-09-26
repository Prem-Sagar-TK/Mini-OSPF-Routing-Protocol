"""
Unit tests for Routing Information Base (RIB) and Longest Prefix Match (LPM).
"""

from mini_ospf.routing.next_hop import NextHop
from mini_ospf.routing.rib import RIB
from mini_ospf.routing.route import Route, RouteType


def test_rib_add_and_lpm() -> None:
    rib = RIB()
    r1 = Route(
        prefix="10.0.0.0",
        prefix_length=8,
        metric=10,
        next_hops=[NextHop(ip_address="192.168.1.1")],
        route_type=RouteType.INTRA_AREA,
    )
    r2 = Route(
        prefix="10.1.2.0",
        prefix_length=24,
        metric=20,
        next_hops=[NextHop(ip_address="192.168.1.2")],
        route_type=RouteType.INTRA_AREA,
    )

    rib.update_from_candidates([r1, r2])

    # 10.1.2.5 should match the more specific /24 route (r2)
    match = rib.lookup_lpm("10.1.2.5")
    assert match is not None
    assert match.prefix_length == 24
    assert match.next_hops[0].ip_address == "192.168.1.2"

    # 10.5.5.5 should match the broader /8 route (r1)
    match_broad = rib.lookup_lpm("10.5.5.5")
    assert match_broad is not None
    assert match_broad.prefix_length == 8

    # 172.16.1.1 should match nothing
    assert rib.lookup_lpm("172.16.1.1") is None


def test_rib_candidate_diff() -> None:
    rib = RIB()
    r1 = Route(prefix="10.0.1.0", prefix_length=24, metric=10)
    r2 = Route(prefix="10.0.2.0", prefix_length=24, metric=10)

    # Initial candidate set
    added, mod, deleted = rib.update_from_candidates([r1, r2])
    assert len(added) == 2
    assert len(mod) == 0
    assert len(deleted) == 0

    # Modify r1 metric, delete r2, add r3
    r1_mod = Route(prefix="10.0.1.0", prefix_length=24, metric=50)
    r3 = Route(prefix="10.0.3.0", prefix_length=24, metric=10)

    added, mod, deleted = rib.update_from_candidates([r1_mod, r3])
    assert len(added) == 1
    assert added[0].prefix == "10.0.3.0"
    assert len(mod) == 1
    assert mod[0].metric == 50
    assert len(deleted) == 1
    assert deleted[0].prefix == "10.0.2.0"
