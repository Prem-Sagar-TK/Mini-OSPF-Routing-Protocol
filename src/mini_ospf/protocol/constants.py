"""
OSPFv2 Protocol Constants (RFC 2328).
"""

from enum import IntEnum, unique

# OSPF Version
OSPF_VERSION: int = 2

# IP Protocol Number for OSPF
IP_PROTOCOL_OSPF: int = 89

# Well-Known Multicast Addresses
ALL_SPF_ROUTERS: str = "224.0.0.5"
ALL_D_ROUTERS: str = "224.0.0.6"

# Fixed Header Sizes in bytes
OSPF_HEADER_LEN: int = 24
LSA_HEADER_LEN: int = 20
ROUTER_LINK_RECORD_LEN: int = 12

# Standard Timers and Constants (Seconds)
DEFAULT_HELLO_INTERVAL: int = 10
DEFAULT_ROUTER_DEAD_INTERVAL: int = 40
DEFAULT_RXMT_INTERVAL: int = 5
DEFAULT_INF_TRANS_DELAY: int = 1
DEFAULT_MIN_LS_INTERVAL: int = 5
DEFAULT_MIN_LS_ARRIVAL: int = 1

LSA_MAX_AGE: int = 3600  # 1 hour
LSA_CHECK_AGE: int = 300  # 5 minutes
LSA_MAX_AGE_DIFF: int = 900  # 15 minutes
LSA_INITIAL_SEQUENCE_NUMBER: int = -0x7FFFFFFF  # 0x80000001 signed 32-bit: -2147483647
LSA_MAX_SEQUENCE_NUMBER: int = 0x7FFFFFFF  # +2147483647

# DBD Exchange Flags
DBD_FLAG_MS: int = 0x01  # Master/Slave
DBD_FLAG_M: int = 0x02   # More
DBD_FLAG_I: int = 0x04   # Init


@unique
class OSPFPacketType(IntEnum):
    HELLO = 1
    DATABASE_DESCRIPTION = 2
    LINK_STATE_REQUEST = 3
    LINK_STATE_UPDATE = 4
    LINK_STATE_ACK = 5


@unique
class LSAType(IntEnum):
    ROUTER = 1
    NETWORK = 2
    SUMMARY_IP = 3
    SUMMARY_ASBR = 4
    AS_EXTERNAL = 5


@unique
class RouterLinkType(IntEnum):
    POINT_TO_POINT = 1
    TRANSIT_NETWORK = 2
    STUB_NETWORK = 3
    VIRTUAL_LINK = 4


@unique
class AuthType(IntEnum):
    NULL = 0
    SIMPLE_PASSWORD = 1
    CRYPTOGRAPHIC = 2


@unique
class InterfaceType(IntEnum):
    POINT_TO_POINT = 1
    BROADCAST = 2
    NON_BROADCAST = 3
    POINT_TO_MULTIPART = 4
    LOOPBACK = 5
