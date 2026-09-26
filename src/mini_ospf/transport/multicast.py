"""
Multicast group helpers for OSPF (224.0.0.5 AllSPFRouters & 224.0.0.6 AllDRouters).
"""

from mini_ospf.protocol.constants import ALL_D_ROUTERS, ALL_SPF_ROUTERS


def is_ospf_multicast(ip_str: str) -> bool:
    return ip_str in (ALL_SPF_ROUTERS, ALL_D_ROUTERS)
