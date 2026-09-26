"""
Unit tests for binary packet serialization and parsing across all OSPF packet types.
"""

import pytest

from mini_ospf.protocol.constants import (
    DBD_FLAG_I,
    DBD_FLAG_M,
    DBD_FLAG_MS,
    LSAType,
    OSPFPacketType,
    RouterLinkType,
)
from mini_ospf.protocol.packet import (
    DatabaseDescriptionPacket,
    HelloPacket,
    LinkStateAckPacket,
    LinkStateRequestPacket,
    LinkStateUpdatePacket,
    LSAHeader,
    LSRRequestItem,
    OSPFHeader,
    RouterLink,
    RouterLSA,
)
from mini_ospf.protocol.parser import PacketParseError, parse_packet
from mini_ospf.protocol.serializer import serialize_packet


def test_hello_roundtrip() -> None:
    hdr = OSPFHeader(
        version=2,
        type=OSPFPacketType.HELLO,
        router_id="1.1.1.1",
        area_id="0.0.0.0",
    )
    hello = HelloPacket(
        header=hdr,
        network_mask="255.255.255.0",
        hello_interval=10,
        router_priority=1,
        dead_interval=40,
        designated_router="10.0.12.1",
        backup_designated_router="10.0.12.2",
        neighbors=["2.2.2.2", "3.3.3.3"],
    )

    raw = serialize_packet(hello)
    parsed = parse_packet(raw)

    assert isinstance(parsed, HelloPacket)
    assert parsed.header.router_id == "1.1.1.1"
    assert parsed.header.area_id == "0.0.0.0"
    assert parsed.network_mask == "255.255.255.0"
    assert parsed.hello_interval == 10
    assert parsed.dead_interval == 40
    assert parsed.designated_router == "10.0.12.1"
    assert parsed.backup_designated_router == "10.0.12.2"
    assert parsed.neighbors == ["2.2.2.2", "3.3.3.3"]


def test_dbd_roundtrip() -> None:
    hdr = OSPFHeader(
        version=2,
        type=OSPFPacketType.DATABASE_DESCRIPTION,
        router_id="2.2.2.2",
        area_id="0.0.0.0",
    )
    lsa_hdr = LSAHeader(
        ls_age=15,
        options=0x02,
        ls_type=LSAType.ROUTER,
        link_state_id="1.1.1.1",
        advertising_router="1.1.1.1",
        ls_sequence_number=-0x7FFFFFFF + 5,
        ls_checksum=0x1234,
        length=36,
    )
    dbd = DatabaseDescriptionPacket(
        header=hdr,
        interface_mtu=1500,
        flags=DBD_FLAG_I | DBD_FLAG_M | DBD_FLAG_MS,
        sequence_number=1001,
        lsa_headers=[lsa_hdr],
    )

    raw = serialize_packet(dbd)
    parsed = parse_packet(raw)

    assert isinstance(parsed, DatabaseDescriptionPacket)
    assert parsed.sequence_number == 1001
    assert parsed.interface_mtu == 1500
    assert parsed.flags == (DBD_FLAG_I | DBD_FLAG_M | DBD_FLAG_MS)
    assert len(parsed.lsa_headers) == 1
    assert parsed.lsa_headers[0].link_state_id == "1.1.1.1"
    assert parsed.lsa_headers[0].ls_sequence_number == -0x7FFFFFFF + 5


def test_router_lsa_and_lsu_roundtrip() -> None:
    lsa_hdr = LSAHeader(
        ls_type=LSAType.ROUTER,
        link_state_id="1.1.1.1",
        advertising_router="1.1.1.1",
        ls_sequence_number=-0x7FFFFFFF,
    )
    links = [
        RouterLink(
            link_id="2.2.2.2",
            link_data="10.0.12.1",
            link_type=RouterLinkType.POINT_TO_POINT,
            metric=10,
        ),
        RouterLink(
            link_id="10.0.12.0",
            link_data="255.255.255.0",
            link_type=RouterLinkType.STUB_NETWORK,
            metric=10,
        ),
    ]
    r_lsa = RouterLSA(header=lsa_hdr, flags=0, num_links=2, links=links)

    lsu = LinkStateUpdatePacket(
        header=OSPFHeader(router_id="1.1.1.1", type=OSPFPacketType.LINK_STATE_UPDATE),
        num_lsas=1,
        lsas=[r_lsa],
    )

    raw = serialize_packet(lsu)
    parsed = parse_packet(raw)

    assert isinstance(parsed, LinkStateUpdatePacket)
    assert len(parsed.lsas) == 1
    p_lsa = parsed.lsas[0]
    assert isinstance(p_lsa, RouterLSA)
    assert p_lsa.header.advertising_router == "1.1.1.1"
    assert len(p_lsa.links) == 2
    assert p_lsa.links[0].link_id == "2.2.2.2"
    assert p_lsa.links[0].metric == 10
    assert p_lsa.links[1].link_type == RouterLinkType.STUB_NETWORK


def test_lsr_and_lsack_roundtrip() -> None:
    # LSR
    lsr = LinkStateRequestPacket(
        header=OSPFHeader(router_id="1.1.1.1", type=OSPFPacketType.LINK_STATE_REQUEST),
        requests=[
            LSRRequestItem(
                ls_type=LSAType.ROUTER,
                link_state_id="2.2.2.2",
                advertising_router="2.2.2.2",
            )
        ],
    )
    raw_lsr = serialize_packet(lsr)
    p_lsr = parse_packet(raw_lsr)
    assert isinstance(p_lsr, LinkStateRequestPacket)
    assert len(p_lsr.requests) == 1
    assert p_lsr.requests[0].link_state_id == "2.2.2.2"

    # LSAck
    lsa_hdr = LSAHeader(
        ls_type=LSAType.ROUTER,
        link_state_id="2.2.2.2",
        advertising_router="2.2.2.2",
    )
    ack = LinkStateAckPacket(
        header=OSPFHeader(router_id="1.1.1.1", type=OSPFPacketType.LINK_STATE_ACK),
        lsa_headers=[lsa_hdr],
    )
    raw_ack = serialize_packet(ack)
    p_ack = parse_packet(raw_ack)
    assert isinstance(p_ack, LinkStateAckPacket)
    assert len(p_ack.lsa_headers) == 1


def test_truncated_packet_raises_error() -> None:
    with pytest.raises(PacketParseError):
        parse_packet(b"\x02\x01\x00\x18")  # Only 4 bytes instead of 24
