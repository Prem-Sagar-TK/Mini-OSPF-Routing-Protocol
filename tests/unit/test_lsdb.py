"""
Unit tests for Link State Database (LSDB), LSA comparison (RFC 2328), and LSA aging.
"""

from mini_ospf.lsdb.aging import LSAgingManager
from mini_ospf.lsdb.database import LinkStateDatabase
from mini_ospf.lsdb.lsa import is_newer_lsa
from mini_ospf.protocol.constants import LSA_MAX_AGE, LSAType
from mini_ospf.protocol.packet import LSAHeader, RouterLSA


def test_lsa_sequence_comparison() -> None:
    hdr1 = LSAHeader(
        ls_type=LSAType.ROUTER,
        link_state_id="1.1.1.1",
        advertising_router="1.1.1.1",
        ls_sequence_number=-0x7FFFFFFF,  # 0x80000001
        ls_checksum=0x1000,
        ls_age=10,
    )
    hdr2 = LSAHeader(
        ls_type=LSAType.ROUTER,
        link_state_id="1.1.1.1",
        advertising_router="1.1.1.1",
        ls_sequence_number=-0x7FFFFFFF + 1,  # 0x80000002 (newer)
        ls_checksum=0x1000,
        ls_age=15,
    )

    assert is_newer_lsa(hdr2, hdr1) is True
    assert is_newer_lsa(hdr1, hdr2) is False


def test_lsa_maxage_comparison() -> None:
    """RFC 2328: An LSA instance with LS age == MaxAge is considered more recent."""
    hdr_norm = LSAHeader(
        ls_sequence_number=100,
        ls_checksum=0x1000,
        ls_age=100,
    )
    hdr_max = LSAHeader(
        ls_sequence_number=100,
        ls_checksum=0x1000,
        ls_age=LSA_MAX_AGE,
    )

    assert is_newer_lsa(hdr_max, hdr_norm) is True
    assert is_newer_lsa(hdr_norm, hdr_max) is False


def test_lsdb_install_and_update() -> None:
    lsdb = LinkStateDatabase()
    lsa1 = RouterLSA(
        header=LSAHeader(
            ls_type=LSAType.ROUTER,
            link_state_id="1.1.1.1",
            advertising_router="1.1.1.1",
            ls_sequence_number=1,
            ls_checksum=0x100,
        )
    )

    installed, reason = lsdb.install(lsa1)
    assert installed is True
    assert reason == "new"
    assert lsdb.count() == 1

    # Duplicate LSA
    installed_dup, reason_dup = lsdb.install(lsa1)
    assert installed_dup is False
    assert reason_dup == "duplicate"

    # Newer LSA
    lsa2 = RouterLSA(
        header=LSAHeader(
            ls_type=LSAType.ROUTER,
            link_state_id="1.1.1.1",
            advertising_router="1.1.1.1",
            ls_sequence_number=2,
            ls_checksum=0x100,
        )
    )
    installed_new, reason_new = lsdb.install(lsa2)
    assert installed_new is True
    assert reason_new == "updated"
    found = lsdb.get(LSAType.ROUTER, "1.1.1.1", "1.1.1.1")
    assert found is not None
    assert found.header.ls_sequence_number == 2


def test_lsdb_aging_and_expiration() -> None:
    lsdb = LinkStateDatabase()
    lsa = RouterLSA(
        header=LSAHeader(
            ls_type=LSAType.ROUTER,
            link_state_id="1.1.1.1",
            advertising_router="1.1.1.1",
            ls_sequence_number=1,
            ls_age=3598,
        )
    )
    lsdb.install(lsa)

    expired_list = []
    aging = LSAgingManager(lsdb, on_max_age=lambda exp_lsa: expired_list.append(exp_lsa))

    # Advance 1s -> age 3599
    aging.tick(1)
    assert lsa.header.ls_age == 3599
    assert len(expired_list) == 0

    # Advance 1s -> age 3600 (MaxAge) -> expired and evicted
    aging.tick(1)
    assert len(expired_list) == 1
    assert lsdb.count() == 0
