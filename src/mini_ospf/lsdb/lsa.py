"""
LSA comparisons and lifecycle models (RFC 2328 Section 12.1.6).
"""

from mini_ospf.protocol.constants import LSA_MAX_AGE, LSA_MAX_AGE_DIFF, LSAType
from mini_ospf.protocol.packet import AnyLSA, LSAHeader


def is_newer_lsa(new_hdr: LSAHeader, current_hdr: LSAHeader) -> bool:
    """
    Compare two LSA instances/headers to determine if 'new_hdr' is more recent
    than 'current_hdr' according to RFC 2328 Section 12.1.6.
    """
    # 1. Compare Sequence Numbers
    if new_hdr.ls_sequence_number > current_hdr.ls_sequence_number:
        return True
    if new_hdr.ls_sequence_number < current_hdr.ls_sequence_number:
        return False

    # 2. Sequence numbers equal; compare Checksums (larger is newer)
    if new_hdr.ls_checksum > current_hdr.ls_checksum:
        return True
    if new_hdr.ls_checksum < current_hdr.ls_checksum:
        return False

    # 3. Checksums equal; check for MaxAge
    if new_hdr.ls_age == LSA_MAX_AGE and current_hdr.ls_age != LSA_MAX_AGE:
        return True
    if current_hdr.ls_age == LSA_MAX_AGE and new_hdr.ls_age != LSA_MAX_AGE:
        return False

    # 4. Check if age difference is significant (> MaxAgeDiff: 900 seconds)
    # The LSA with the smaller LS age is considered more recent.
    if abs(new_hdr.ls_age - current_hdr.ls_age) > LSA_MAX_AGE_DIFF:
        return new_hdr.ls_age < current_hdr.ls_age

    # Otherwise, considered same instance
    return False


def is_same_lsa_instance(hdr1: LSAHeader, hdr2: LSAHeader) -> bool:
    """Return True if both headers represent the identical instance."""
    return (
        hdr1.ls_sequence_number == hdr2.ls_sequence_number
        and hdr1.ls_checksum == hdr2.ls_checksum
        and not is_newer_lsa(hdr1, hdr2)
        and not is_newer_lsa(hdr2, hdr1)
    )


def extract_lsa_header(lsa: AnyLSA) -> LSAHeader:
    """Safely extract LSAHeader from any LSA object."""
    return lsa.header


def lsa_key(ls_type: LSAType, link_state_id: str, adv_router: str) -> tuple[LSAType, str, str]:
    """Generate canonical 3-tuple key for LSDB lookup."""
    return (ls_type, link_state_id, adv_router)
