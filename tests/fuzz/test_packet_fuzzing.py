"""
Fuzz testing for binary packet parsing, boundary bounds, and malformed payload resilience.
"""

import random

from mini_ospf.protocol.packet import HelloPacket, OSPFHeader
from mini_ospf.protocol.parser import PacketParseError, parse_packet
from mini_ospf.protocol.serializer import serialize_packet
from mini_ospf.protocol.validation import ValidationError, validate_raw_packet


def test_fuzz_random_byte_streams() -> None:
    """Ensure parser gracefully rejects arbitrary random byte sequences without crashing."""
    rng = random.Random(42)

    for _ in range(500):
        length = rng.randint(0, 1024)
        garbage = bytes(rng.getrandbits(8) for _ in range(length))
        try:
            validate_raw_packet(garbage)
            parse_packet(garbage)
        except (ValidationError, PacketParseError, ValueError):
            pass  # Expected safe rejection


def test_fuzz_mutated_valid_packets() -> None:
    """Mutate valid packets with bitflips and byte replacements; parser must handle cleanly."""
    base_hello = HelloPacket(
        header=OSPFHeader(router_id="1.1.1.1", area_id="0.0.0.0"),
        network_mask="255.255.255.0",
        neighbors=["2.2.2.2"],
    )
    raw = bytearray(serialize_packet(base_hello))
    rng = random.Random(1337)

    for _ in range(500):
        mutated = bytearray(raw)
        # Apply 1 to 5 random byte corruptions
        num_mutations = rng.randint(1, 5)
        for _ in range(num_mutations):
            pos = rng.randint(0, len(mutated) - 1)
            mutated[pos] ^= rng.randint(1, 255)

        try:
            validate_raw_packet(mutated)
            parse_packet(mutated)
        except (ValidationError, PacketParseError, ValueError):
            pass


def test_fuzz_truncation_boundaries() -> None:
    """Truncate valid packet at every single byte boundary."""
    base_hello = HelloPacket(
        header=OSPFHeader(router_id="1.1.1.1", area_id="0.0.0.0"),
        network_mask="255.255.255.0",
        neighbors=["2.2.2.2", "3.3.3.3"],
    )
    raw = serialize_packet(base_hello)

    for i in range(len(raw)):
        truncated = raw[:i]
        try:
            validate_raw_packet(truncated)
            parse_packet(truncated)
        except (ValidationError, PacketParseError, ValueError):
            pass
