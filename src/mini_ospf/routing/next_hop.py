"""
Next-hop data structures for routes and FIB installation.
"""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class NextHop:
    ip_address: str = ""
    interface_name: str = ""
    weight: int = 1

    def __str__(self) -> str:
        if self.ip_address and self.interface_name:
            return f"via {self.ip_address} dev {self.interface_name}"
        elif self.ip_address:
            return f"via {self.ip_address}"
        elif self.interface_name:
            return f"dev {self.interface_name}"
        return "direct"
