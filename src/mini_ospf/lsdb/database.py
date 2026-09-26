"""
Link State Database (LSDB) Subsystem (RFC 2328 Section 12).
"""

import logging
from collections.abc import Callable

from mini_ospf.lsdb.lsa import is_newer_lsa, is_same_lsa_instance
from mini_ospf.protocol.constants import LSA_MAX_AGE, LSAType
from mini_ospf.protocol.packet import AnyLSA, LSAHeader, NetworkLSA, RouterLSA, SummaryLSA

logger = logging.getLogger("mini_ospf.lsdb")


class LinkStateDatabase:
    """
    Structured in-memory Link State Database storing and indexing all active LSAs for an area.
    Indexed by composite key: (LSAType, link_state_id, advertising_router).
    """

    def __init__(self, area_id: str = "0.0.0.0") -> None:
        self.area_id: str = area_id
        self._database: dict[tuple[LSAType, str, str], AnyLSA] = {}
        self._listeners: list[Callable[[AnyLSA, str], None]] = []

    def add_change_listener(self, listener: Callable[[AnyLSA, str], None]) -> None:
        """Register a callback when an LSA is installed, updated, or deleted."""
        self._listeners.append(listener)

    def _notify(self, lsa: AnyLSA, action: str) -> None:
        for cb in self._listeners:
            try:
                cb(lsa, action)
            except Exception as e:
                logger.error("LSDB listener failed: %s", e)

    def get(
        self, ls_type: LSAType, link_state_id: str, advertising_router: str
    ) -> AnyLSA | None:
        """Lookup an LSA by its full 3-tuple identifier."""
        return self._database.get((ls_type, link_state_id, advertising_router))

    def get_by_header(self, hdr: LSAHeader) -> AnyLSA | None:
        return self._database.get(hdr.key)

    def install(self, lsa: AnyLSA) -> tuple[bool, str]:
        """
        Install or update an LSA in the database.
        Returns (installed: bool, reason: str).
        """
        key = lsa.header.key
        current = self._database.get(key)

        if current is None:
            # If current does not exist, install if not already at MaxAge
            if lsa.header.ls_age >= LSA_MAX_AGE:
                return False, "ignored_max_age_on_empty"
            self._database[key] = lsa
            self._notify(lsa, "added")
            return True, "new"

        if is_same_lsa_instance(lsa.header, current.header):
            return False, "duplicate"

        if is_newer_lsa(lsa.header, current.header):
            if lsa.header.ls_age >= LSA_MAX_AGE:
                # MaxAge flush
                self._database[key] = lsa
                self._notify(lsa, "flushed_max_age")
                return True, "max_age_flush"

            self._database[key] = lsa
            self._notify(lsa, "updated")
            return True, "updated"

        return False, "older"

    def remove(self, key: tuple[LSAType, str, str]) -> AnyLSA | None:
        """Remove an LSA from the LSDB."""
        lsa = self._database.pop(key, None)
        if lsa:
            self._notify(lsa, "deleted")
        return lsa

    def all_lsas(self) -> list[AnyLSA]:
        """Return a copy of all current LSAs."""
        return list(self._database.values())

    def get_headers(self) -> list[LSAHeader]:
        """Return LSA headers for all LSAs currently in the database."""
        return [lsa.header for lsa in self._database.values()]

    def get_router_lsas(self) -> list[RouterLSA]:
        return [lsa for lsa in self._database.values() if isinstance(lsa, RouterLSA)]

    def get_network_lsas(self) -> list[NetworkLSA]:
        return [lsa for lsa in self._database.values() if isinstance(lsa, NetworkLSA)]

    def get_summary_lsas(self) -> list[SummaryLSA]:
        return [lsa for lsa in self._database.values() if isinstance(lsa, SummaryLSA)]

    def count(self) -> int:
        return len(self._database)

    def clear(self) -> None:
        self._database.clear()
