"""
Security and Resource Limits for Mini-OSPF Daemon.
"""

import time
from dataclasses import dataclass


@dataclass(slots=True)
class ResourceLimits:
    max_lsas_in_db: int = 10000
    max_neighbors_per_interface: int = 255
    max_packet_rate_per_sec: int = 500
    max_payload_bytes: int = 65535


class RateLimiter:
    """Token-bucket rate limiter to mitigate packet floods and DoS."""

    def __init__(self, rate_per_sec: int = 500, burst: int = 1000) -> None:
        self.rate = rate_per_sec
        self.burst = burst
        self.tokens: float = float(burst)
        self.last_check: float = time.monotonic()

    def allow(self, cost: float = 1.0) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_check
        self.last_check = now

        self.tokens = min(float(self.burst), self.tokens + elapsed * self.rate)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False
