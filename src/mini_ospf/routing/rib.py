"""
Routing Information Base (RIB) and Longest Prefix Match (LPM).
"""

import ipaddress
import logging
from collections.abc import Callable

from mini_ospf.routing.route import Route

logger = logging.getLogger("mini_ospf.routing.rib")


class RIB:
    """
    In-memory Routing Information Base storing active IP routes computed by SPF.
    Provides Longest Prefix Matching (LPM) and generates diffs (added/modified/deleted)
    to drive kernel FIB updates.
    """

    def __init__(self) -> None:
        self._table: dict[str, Route] = {}  # "prefix/prefix_len" -> Route
        self._listeners: list[Callable[[list[Route], list[Route], list[Route]], None]] = []

    def add_listener(
        self, listener: Callable[[list[Route], list[Route], list[Route]], None]
    ) -> None:
        self._listeners.append(listener)

    def get_route(self, prefix: str, prefix_length: int) -> Route | None:
        return self._table.get(f"{prefix}/{prefix_length}")

    def all_routes(self) -> list[Route]:
        return list(self._table.values())

    def count(self) -> int:
        return len(self._table)

    def lookup_lpm(self, ip_str: str) -> Route | None:
        """
        Perform Longest Prefix Match (LPM) against all active routes in the RIB.
        """
        try:
            target_ip = ipaddress.IPv4Address(ip_str)
        except ValueError:
            return None

        best_match: Route | None = None
        best_prefix_len = -1

        for route in self._table.values():
            try:
                network = ipaddress.IPv4Network(f"{route.prefix}/{route.prefix_length}", strict=False)
                if target_ip in network:
                    if route.prefix_length > best_prefix_len:
                        best_prefix_len = route.prefix_length
                        best_match = route
            except ValueError:
                continue

        return best_match

    def update_from_candidates(
        self, new_candidates: list[Route]
    ) -> tuple[list[Route], list[Route], list[Route]]:
        """
        Synchronize the RIB with new SPF route candidates.
        Returns: (added_routes, modified_routes, deleted_routes).
        """
        new_map: dict[str, Route] = {r.destination: r for r in new_candidates}
        added: list[Route] = []
        modified: list[Route] = []
        deleted: list[Route] = []

        # Find deleted routes
        for dest, current_route in list(self._table.items()):
            if dest not in new_map:
                deleted.append(current_route)
                del self._table[dest]

        # Find added or modified routes
        for dest, candidate in new_map.items():
            if dest not in self._table:
                self._table[dest] = candidate
                added.append(candidate)
            else:
                existing = self._table[dest]
                # Check if metric or next-hops changed
                if existing.metric != candidate.metric or existing.next_hops != candidate.next_hops:
                    self._table[dest] = candidate
                    modified.append(candidate)

        if added or modified or deleted:
            for cb in self._listeners:
                try:
                    cb(added, modified, deleted)
                except Exception as e:
                    logger.error("RIB change listener error: %s", e)

        return added, modified, deleted

    def clear(self) -> None:
        self._table.clear()
