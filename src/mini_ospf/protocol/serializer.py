"""
OSPFv2 Packet and LSA Binary Serializer (RFC 2328).
"""

import socket
import struct

from mini_ospf.protocol.checksum import fletcher16_checksum, ip_checksum
from mini_ospf.protocol.constants import (
    LSA_HEADER_LEN,
    OSPF_HEADER_LEN,
    OSPFPacketType,
)
from mini_ospf.protocol.packet import (
    AnyLSA,
    DatabaseDescriptionPacket,
    HelloPacket,
    LinkStateAckPacket,
    LinkStateRequestPacket,
    LinkStateUpdatePacket,
    LSAHeader,
    NetworkLSA,
    OSPFHeader,
    RouterLSA,
    SummaryLSA,
)


def _ip_to_bytes(ip_str: str) -> bytes:
    try:
        return socket.inet_aton(ip_str)
    except OSError:
        return b"\x00\x00\x00\x00"


def serialize_lsa_header(hdr: LSAHeader, length_override: int | None = None) -> bytearray:
    """Serialize 20-byte LSA Header into a bytearray."""
    length = length_override if length_override is not None else hdr.length
    # struct: LS age (2B), options (1B), ls_type (1B), ls_id (4B), adv_rtr (4B), seq (4B signed), checksum (2B), length (2B)
    return bytearray(
        struct.pack(
            "!HBB4s4siHH",
            hdr.ls_age,
            hdr.options,
            int(hdr.ls_type),
            _ip_to_bytes(hdr.link_state_id),
            _ip_to_bytes(hdr.advertising_router),
            hdr.ls_sequence_number,
            hdr.ls_checksum,
            length,
        )
    )


def serialize_lsa(lsa: AnyLSA) -> bytes:
    """Serialize a complete LSA (Header + Body) and compute its Fletcher-16 checksum."""
    if isinstance(lsa, RouterLSA):
        # Body: flags (1B), reserved (1B), num_links (2B), then links
        body = bytearray(struct.pack("!BBH", lsa.flags, 0, len(lsa.links)))
        for link in lsa.links:
            body.extend(
                struct.pack(
                    "!4s4sBBH",
                    _ip_to_bytes(link.link_id),
                    _ip_to_bytes(link.link_data),
                    int(link.link_type),
                    link.num_tos,
                    link.metric,
                )
            )
    elif isinstance(lsa, NetworkLSA):
        body = bytearray(struct.pack("!4s", _ip_to_bytes(lsa.network_mask)))
        for rtr in lsa.attached_routers:
            body.extend(_ip_to_bytes(rtr))
    elif isinstance(lsa, SummaryLSA):
        # Metric is 24-bit
        metric_bytes = (lsa.metric & 0xFFFFFF).to_bytes(3, byteorder="big")
        body = bytearray(struct.pack("!4sB", _ip_to_bytes(lsa.network_mask), 0) + metric_bytes)
    else:
        raise ValueError(f"Unsupported LSA type: {type(lsa)}")

    total_len = LSA_HEADER_LEN + len(body)
    lsa.header.length = total_len
    header_bytes = serialize_lsa_header(lsa.header, length_override=total_len)
    full_lsa = header_bytes + body

    # Compute Fletcher-16 checksum over full LSA (excluding age) and patch header
    c1, c2 = fletcher16_checksum(full_lsa, offset=16)
    full_lsa[16] = c1
    full_lsa[17] = c2
    lsa.header.ls_checksum = (c1 << 8) | c2

    return bytes(full_lsa)


def serialize_ospf_header(hdr: OSPFHeader, total_packet_len: int) -> bytearray:
    """Serialize 24-byte OSPF Header with checksum = 0."""
    auth = hdr.auth_data if len(hdr.auth_data) == 8 else (hdr.auth_data + b"\x00" * 8)[:8]
    return bytearray(
        struct.pack(
            "!BBH4s4sHH8s",
            hdr.version,
            int(hdr.type),
            total_packet_len,
            _ip_to_bytes(hdr.router_id),
            _ip_to_bytes(hdr.area_id),
            0,  # Zero checksum initially
            hdr.autype,
            auth,
        )
    )


def serialize_packet(
    pkt: HelloPacket
    | DatabaseDescriptionPacket
    | LinkStateRequestPacket
    | LinkStateUpdatePacket
    | LinkStateAckPacket,
) -> bytes:
    """
    Serialize any OSPF packet into raw wire bytes, calculating the IP header checksum.
    """
    if isinstance(pkt, HelloPacket):
        body = bytearray(
            struct.pack(
                "!4sHBB4s4s4s",
                _ip_to_bytes(pkt.network_mask),
                pkt.hello_interval,
                pkt.options,
                pkt.router_priority,
                pkt.dead_interval.to_bytes(4, "big"),
                _ip_to_bytes(pkt.designated_router),
                _ip_to_bytes(pkt.backup_designated_router),
            )
        )
        for neigh in pkt.neighbors:
            body.extend(_ip_to_bytes(neigh))
        hdr = pkt.header
        hdr.type = OSPFPacketType.HELLO

    elif isinstance(pkt, DatabaseDescriptionPacket):
        body = bytearray(
            struct.pack(
                "!HBBI",
                pkt.interface_mtu,
                pkt.options,
                pkt.flags,
                pkt.sequence_number,
            )
        )
        for lsa_hdr in pkt.lsa_headers:
            body.extend(serialize_lsa_header(lsa_hdr))
        hdr = pkt.header
        hdr.type = OSPFPacketType.DATABASE_DESCRIPTION

    elif isinstance(pkt, LinkStateRequestPacket):
        body = bytearray()
        for req in pkt.requests:
            body.extend(
                struct.pack(
                    "!I4s4s",
                    int(req.ls_type),
                    _ip_to_bytes(req.link_state_id),
                    _ip_to_bytes(req.advertising_router),
                )
            )
        hdr = pkt.header
        hdr.type = OSPFPacketType.LINK_STATE_REQUEST

    elif isinstance(pkt, LinkStateUpdatePacket):
        body = bytearray(struct.pack("!I", len(pkt.lsas)))
        for lsa in pkt.lsas:
            body.extend(serialize_lsa(lsa))
        hdr = pkt.header
        hdr.type = OSPFPacketType.LINK_STATE_UPDATE

    elif isinstance(pkt, LinkStateAckPacket):
        body = bytearray()
        for lsa_hdr in pkt.lsa_headers:
            body.extend(serialize_lsa_header(lsa_hdr))
        hdr = pkt.header
        hdr.type = OSPFPacketType.LINK_STATE_ACK

    else:
        raise ValueError(f"Unknown packet type: {type(pkt)}")

    total_len = OSPF_HEADER_LEN + len(body)
    hdr.packet_length = total_len
    raw_header = serialize_ospf_header(hdr, total_len)

    raw_packet = raw_header + body

    # Calculate 16-bit 1's complement Internet Checksum for the whole packet
    # (Excluding 64-bit authentication field per RFC 2328 for Cryptographic, or standard)
    csum = ip_checksum(raw_packet)
    struct.pack_into("!H", raw_packet, 12, csum)
    hdr.checksum = csum

    return bytes(raw_packet)
