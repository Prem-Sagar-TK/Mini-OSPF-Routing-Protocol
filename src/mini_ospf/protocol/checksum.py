"""
Checksum algorithms for OSPF packets (Internet Checksum RFC 1071)
and LSA Headers (Fletcher-16 Checksum RFC 2328 / RFC 905).
"""


def ip_checksum(data: bytes | bytearray | memoryview) -> int:
    """
    Calculate the standard 16-bit one's complement Internet checksum (RFC 1071).
    Used for OSPF packet headers.
    """
    if len(data) % 2 == 1:
        data = bytes(data) + b"\x00"

    total = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        total += word
        while total > 0xFFFF:
            total = (total & 0xFFFF) + (total >> 16)

    return (~total) & 0xFFFF


def verify_ip_checksum(data: bytes | bytearray | memoryview) -> bool:
    """
    Verify the 16-bit Internet checksum over a packet.
    When verified across the entire packet including the checksum field,
    the result should be 0 (or ~0 in 1's complement = 0x0000).
    """
    return ip_checksum(data) == 0


def fletcher16_checksum(data: bytes | bytearray | memoryview, offset: int = 16) -> tuple[int, int]:
    """
    Calculate Fletcher-16 checksum for an LSA per RFC 2328 Section 12.1.7 / RFC 905.
    LSA age (first 2 bytes) is excluded from the checksum computation.
    The checksum bytes (x and y) are placed at 'offset' (default byte 16 & 17 of LSA).

    Returns (b1, b2) representing the two 8-bit checksum bytes.
    """
    # Exclude the 2-byte LS age field at index 0 and 1
    lsa_body = memoryview(data)[2:]
    k = len(lsa_body)
    # The offset in lsa_body where the checksum bytes sit (16 - 2 = 14)
    c_offset = offset - 2

    c0 = 0
    c1 = 0

    for i in range(k):
        if i == c_offset or i == c_offset + 1:
            # Checksum field is treated as 0 during computation
            val = 0
        else:
            val = lsa_body[i]
        c0 = (c0 + val) % 255
        c1 = (c1 + c0) % 255

    # Formulas from RFC 905 / RFC 2328
    # x = ((k - c_offset - 1) * c0 - c1) % 255
    # y = (c1 - (k - c_offset) * c0) % 255
    x = int(((k - c_offset - 1) * c0 - c1) % 255)
    if x <= 0:
        x += 255

    y = int((510 - c0 - x) % 255)
    if y <= 0:
        y += 255

    return x, y


def verify_fletcher16(data: bytes | bytearray | memoryview) -> bool:
    """
    Verify Fletcher-16 checksum of an LSA (RFC 2328 Section 12.1.7).
    Excludes the first 2 bytes (LS Age).
    """
    if len(data) < 20:
        return False
    lsa_body = memoryview(data)[2:]
    c0 = 0
    c1 = 0
    for byte in lsa_body:
        c0 = (c0 + byte) % 255
        c1 = (c1 + c0) % 255
    return c0 == 0 and c1 == 0
