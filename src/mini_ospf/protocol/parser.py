"""
OSPFv2 Packet and LSA Binary Parser (RFC 2328).
"""

import socket
import struct

from mini_ospf.protocol.constants import (
    LSA_HEADER_LEN,
    OSPF_HEADER_LEN,
    ROUTER_LINK_RECORD_LEN,
    LSAType,
    OSPFPacketType,
    RouterLinkType,
)
from mini_ospf.protocol.packet import (
    AnyLSA,
    DatabaseDescriptionPacket,
    HelloPacket,
    LinkStateAckPacket,
    LinkStateRequestPacket,
    LinkStateUpdatePacket,
    LSAHeader,
    LSRRequestItem,
    NetworkLSA,
    OSPFHeader,
    RouterLink,
    RouterLSA,
    SummaryLSA,
)


class PacketParseError(Exception):
    """Raised when an OSPF packet is malformed, truncated, or invalid."""


def _bytes_to_ip(raw: bytes) -> str:
    return socket.inet_ntoa(raw)


def parse_ospf_header(data: bytes | bytearray | memoryview) -> OSPFHeader:
    """Parse 24-byte OSPF common header."""
    if len(data) < OSPF_HEADER_LEN:
        raise PacketParseError(f"Packet too short for OSPF header: {len(data)} < {OSPF_HEADER_LEN}")

    version, ptype_raw, pkt_len, rtr_bytes, area_bytes, checksum, autype, auth_data = (
        struct.unpack_from("!BBH4s4sHH8s", data, 0)
    )

    try:
        ptype = OSPFPacketType(ptype_raw)
    except ValueError as e:
        raise PacketParseError(f"Unknown OSPF packet type: {ptype_raw}") from e

    return OSPFHeader(
        version=version,
        type=ptype,
        packet_length=pkt_len,
        router_id=_bytes_to_ip(rtr_bytes),
        area_id=_bytes_to_ip(area_bytes),
        checksum=checksum,
        autype=autype,
        auth_data=auth_data,
    )


def parse_lsa_header(data: bytes | bytearray | memoryview, offset: int = 0) -> LSAHeader:
    """Parse 20-byte LSA header starting at given offset."""
    if len(data) - offset < LSA_HEADER_LEN:
        raise PacketParseError(
            f"Buffer too short for LSA header: {len(data) - offset} < {LSA_HEADER_LEN}"
        )

    ls_age, options, ls_type_raw, id_bytes, adv_bytes, seq_num, checksum, length = (
        struct.unpack_from("!HBB4s4siHH", data, offset)
    )

    try:
        ls_type = LSAType(ls_type_raw)
    except ValueError as e:
        raise PacketParseError(f"Unknown LSA type: {ls_type_raw}") from e

    return LSAHeader(
        ls_age=ls_age,
        options=options,
        ls_type=ls_type,
        link_state_id=_bytes_to_ip(id_bytes),
        advertising_router=_bytes_to_ip(adv_bytes),
        ls_sequence_number=seq_num,
        ls_checksum=checksum,
        length=length,
    )


def parse_lsa(data: bytes | bytearray | memoryview, offset: int = 0) -> tuple[AnyLSA, int]:
    """
    Parse a complete LSA from buffer at offset.
    Returns tuple of (LSA dataclass, consumed_bytes).
    """
    hdr = parse_lsa_header(data, offset)
    lsa_len = hdr.length
    if lsa_len < LSA_HEADER_LEN or len(data) - offset < lsa_len:
        raise PacketParseError(
            f"LSA advertised length {lsa_len} exceeds buffer size {len(data) - offset}"
        )

    body_offset = offset + LSA_HEADER_LEN
    body_len = lsa_len - LSA_HEADER_LEN

    if hdr.ls_type == LSAType.ROUTER:
        if body_len < 4:
            raise PacketParseError("Router-LSA body too short for header fields")
        flags, _, num_links = struct.unpack_from("!BBH", data, body_offset)
        expected_link_bytes = num_links * ROUTER_LINK_RECORD_LEN
        if body_len - 4 < expected_link_bytes:
            raise PacketParseError(
                f"Router-LSA links truncated: expected {expected_link_bytes} bytes, got {body_len - 4}"
            )

        links: list[RouterLink] = []
        cur = body_offset + 4
        for _ in range(num_links):
            link_id, link_data, link_type_raw, num_tos, metric = struct.unpack_from(
                "!4s4sBBH", data, cur
            )
            try:
                link_type = RouterLinkType(link_type_raw)
            except ValueError:
                link_type = RouterLinkType.POINT_TO_POINT

            links.append(
                RouterLink(
                    link_id=_bytes_to_ip(link_id),
                    link_data=_bytes_to_ip(link_data),
                    link_type=link_type,
                    num_tos=num_tos,
                    metric=metric,
                )
            )
            cur += ROUTER_LINK_RECORD_LEN

        return RouterLSA(header=hdr, flags=flags, num_links=num_links, links=links), lsa_len

    elif hdr.ls_type == LSAType.NETWORK:
        if body_len < 4:
            raise PacketParseError("Network-LSA body too short")
        mask_bytes = data[body_offset : body_offset + 4]
        attached: list[str] = []
        for i in range(body_offset + 4, offset + lsa_len, 4):
            if i + 4 <= offset + lsa_len:
                attached.append(_bytes_to_ip(bytes(data[i : i + 4])))
        return (
            NetworkLSA(
                header=hdr, network_mask=_bytes_to_ip(bytes(mask_bytes)), attached_routers=attached
            ),
            lsa_len,
        )

    elif hdr.ls_type in (LSAType.SUMMARY_IP, LSAType.SUMMARY_ASBR):
        if body_len < 8:
            raise PacketParseError("Summary-LSA body too short")
        mask_bytes = data[body_offset : body_offset + 4]
        metric_raw = data[body_offset + 5 : body_offset + 8]
        metric = int.from_bytes(metric_raw, byteorder="big")
        return (
            SummaryLSA(
                header=hdr, network_mask=_bytes_to_ip(bytes(mask_bytes)), metric=metric
            ),
            lsa_len,
        )

    else:
        # Fallback for other LSA types
        return RouterLSA(header=hdr, flags=0, num_links=0, links=[]), lsa_len


def parse_packet(
    data: bytes | bytearray | memoryview,
) -> (
    HelloPacket
    | DatabaseDescriptionPacket
    | LinkStateRequestPacket
    | LinkStateUpdatePacket
    | LinkStateAckPacket
):
    """
    Parse an entire OSPF packet from raw bytes into its corresponding typed dataclass.
    """
    hdr = parse_ospf_header(data)
    if len(data) < hdr.packet_length:
        raise PacketParseError(
            f"Buffer length {len(data)} is less than OSPF packet header length {hdr.packet_length}"
        )

    # Slice strictly to packet_length
    pkt_bytes = memoryview(data)[: hdr.packet_length]
    body_offset = OSPF_HEADER_LEN
    body_len = hdr.packet_length - OSPF_HEADER_LEN

    if hdr.type == OSPFPacketType.HELLO:
        if body_len < 20:
            raise PacketParseError(f"Hello packet body too short: {body_len} < 20")
        mask_raw, hello_int, opts, prio, dead_raw, dr_raw, bdr_raw = struct.unpack_from(
            "!4sHBB4s4s4s", pkt_bytes, body_offset
        )
        dead_interval = int.from_bytes(dead_raw, "big")

        neighbors: list[str] = []
        cur = body_offset + 20
        while cur + 4 <= hdr.packet_length:
            neighbors.append(_bytes_to_ip(bytes(pkt_bytes[cur : cur + 4])))
            cur += 4

        return HelloPacket(
            header=hdr,
            network_mask=_bytes_to_ip(mask_raw),
            hello_interval=hello_int,
            options=opts,
            router_priority=prio,
            dead_interval=dead_interval,
            designated_router=_bytes_to_ip(dr_raw),
            backup_designated_router=_bytes_to_ip(bdr_raw),
            neighbors=neighbors,
        )

    elif hdr.type == OSPFPacketType.DATABASE_DESCRIPTION:
        if body_len < 8:
            raise PacketParseError(f"DBD packet body too short: {body_len} < 8")
        mtu, opts, flags, seq = struct.unpack_from("!HBBI", pkt_bytes, body_offset)

        lsa_headers: list[LSAHeader] = []
        cur = body_offset + 8
        while cur + LSA_HEADER_LEN <= hdr.packet_length:
            lsa_hdr = parse_lsa_header(pkt_bytes, cur)
            lsa_headers.append(lsa_hdr)
            cur += LSA_HEADER_LEN

        return DatabaseDescriptionPacket(
            header=hdr,
            interface_mtu=mtu,
            options=opts,
            flags=flags,
            sequence_number=seq,
            lsa_headers=lsa_headers,
        )

    elif hdr.type == OSPFPacketType.LINK_STATE_REQUEST:
        requests: list[LSRRequestItem] = []
        cur = body_offset
        while cur + 12 <= hdr.packet_length:
            ls_type_raw, id_raw, adv_raw = struct.unpack_from("!I4s4s", pkt_bytes, cur)
            try:
                ls_type = LSAType(ls_type_raw)
            except ValueError:
                ls_type = LSAType.ROUTER
            requests.append(
                LSRRequestItem(
                    ls_type=ls_type,
                    link_state_id=_bytes_to_ip(id_raw),
                    advertising_router=_bytes_to_ip(adv_raw),
                )
            )
            cur += 12

        return LinkStateRequestPacket(header=hdr, requests=requests)

    elif hdr.type == OSPFPacketType.LINK_STATE_UPDATE:
        if body_len < 4:
            raise PacketParseError(f"LSU body too short: {body_len} < 4")
        (num_lsas,) = struct.unpack_from("!I", pkt_bytes, body_offset)
        lsas: list[AnyLSA] = []
        cur = body_offset + 4
        for _ in range(num_lsas):
            if cur >= hdr.packet_length:
                break
            lsa_obj, consumed = parse_lsa(pkt_bytes, cur)
            lsas.append(lsa_obj)
            cur += consumed

        return LinkStateUpdatePacket(header=hdr, num_lsas=len(lsas), lsas=lsas)

    elif hdr.type == OSPFPacketType.LINK_STATE_ACK:
        lsa_headers = []
        cur = body_offset
        while cur + LSA_HEADER_LEN <= hdr.packet_length:
            lsa_hdr = parse_lsa_header(pkt_bytes, cur)
            lsa_headers.append(lsa_hdr)
            cur += LSA_HEADER_LEN

        return LinkStateAckPacket(header=hdr, lsa_headers=lsa_headers)

    else:
        raise PacketParseError(f"Unsupported packet type {hdr.type}")
