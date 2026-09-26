"""
Defensive packet bounds and security sanity guards.
"""

from mini_ospf.security.limits import ResourceLimits


class SecurityGuardError(Exception):
    """Raised when an incoming packet breaches security bounds."""


def check_packet_limits(data: bytes | bytearray | memoryview, limits: ResourceLimits) -> None:
    """Ensure packet does not exceed maximum allowable payload size."""
    if len(data) > limits.max_payload_bytes:
        raise SecurityGuardError(
            f"Packet size ({len(data)} B) exceeds maximum limit ({limits.max_payload_bytes} B)"
        )
