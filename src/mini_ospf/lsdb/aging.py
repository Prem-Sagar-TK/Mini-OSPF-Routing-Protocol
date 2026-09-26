"""
LSA Aging and MaxAge Expiration Subsystem (RFC 2328 Section 14).
"""

import logging
from collections.abc import Callable

from mini_ospf.lsdb.database import LinkStateDatabase
from mini_ospf.protocol.constants import LSA_MAX_AGE
from mini_ospf.protocol.packet import AnyLSA

logger = logging.getLogger("mini_ospf.lsdb.aging")


class LSAgingManager:
    """
    Manages periodic aging of LSAs stored in an LSDB.
    Increments age each second and triggers MaxAge eviction callbacks.
    """

    def __init__(
        self,
        lsdb: LinkStateDatabase,
        on_max_age: Callable[[AnyLSA], None] | None = None,
    ) -> None:
        self.lsdb = lsdb
        self.on_max_age = on_max_age

    def tick(self, seconds: int = 1) -> list[AnyLSA]:
        """
        Advance LSA age across all LSAs in the database by 'seconds'.
        Returns list of newly expired LSAs reaching LSA_MAX_AGE.
        """
        expired: list[AnyLSA] = []
        for lsa in self.lsdb.all_lsas():
            # If already at max age, leave it
            if lsa.header.ls_age >= LSA_MAX_AGE:
                continue

            lsa.header.ls_age = min(LSA_MAX_AGE, lsa.header.ls_age + seconds)
            if lsa.header.ls_age >= LSA_MAX_AGE:
                expired.append(lsa)
                if self.on_max_age:
                    try:
                        self.on_max_age(lsa)
                    except Exception as e:
                        logger.error("Error in on_max_age handler: %s", e)

        # Evict or flush expired LSAs after notification
        for lsa in expired:
            self.lsdb.remove(lsa.header.key)

        return expired
