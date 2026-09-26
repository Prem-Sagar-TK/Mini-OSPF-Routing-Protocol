"""
Unit tests for OSPF IP checksum (RFC 1071) and Fletcher-16 checksum (RFC 2328 / RFC 905).
"""

from mini_ospf.protocol.checksum import (
    fletcher16_checksum,
    ip_checksum,
    verify_fletcher16,
    verify_ip_checksum,
)


def test_ip_checksum_basic() -> None:
    data = b"\x02\x01\x00\x18\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    csum = ip_checksum(data)
    assert isinstance(csum, int)
    assert 0 <= csum <= 0xFFFF

    # When checksum is placed at offset 12:14, verification across entire packet should pass
    patched = bytearray(data)
    patched[12] = (csum >> 8) & 0xFF
    patched[13] = csum & 0xFF
    assert verify_ip_checksum(patched) is True


def test_fletcher16_checksum() -> None:
    # 20-byte dummy LSA Header: Age(2B), Opt(1B), Type(1B), LSID(4B), AdvRtr(4B), Seq(4B), Csum(2B), Len(2B)
    raw_lsa = bytearray(
        b"\x00\x00\x02\x01\x01\x01\x01\x01\x01\x01\x01\x01\x80\x00\x00\x01\x00\x00\x00\x14"
    )
    c1, c2 = fletcher16_checksum(raw_lsa, offset=16)
    raw_lsa[16] = c1
    raw_lsa[17] = c2

    assert verify_fletcher16(raw_lsa) is True


def test_fletcher16_age_independence() -> None:
    """RFC 2328: LSA Age is excluded from checksum; modifying age should not invalidate checksum."""
    raw_lsa = bytearray(
        b"\x00\x00\x02\x01\x01\x01\x01\x01\x01\x01\x01\x01\x80\x00\x00\x01\x00\x00\x00\x14"
    )
    c1, c2 = fletcher16_checksum(raw_lsa, offset=16)
    raw_lsa[16] = c1
    raw_lsa[17] = c2

    # Change age from 0 to 1200 seconds
    raw_lsa[0] = (1200 >> 8) & 0xFF
    raw_lsa[1] = 1200 & 0xFF
    assert verify_fletcher16(raw_lsa) is True


def test_corrupted_fletcher16_fails() -> None:
    raw_lsa = bytearray(
        b"\x00\x00\x02\x01\x01\x01\x01\x01\x01\x01\x01\x01\x80\x00\x00\x01\x00\x00\x00\x14"
    )
    c1, c2 = fletcher16_checksum(raw_lsa, offset=16)
    raw_lsa[16] = c1
    raw_lsa[17] = c2

    # Corrupt a byte in the LSA ID
    raw_lsa[5] ^= 0xFF
    assert verify_fletcher16(raw_lsa) is False
