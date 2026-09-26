"""
Asyncio Packet Sender.
"""

import logging

from mini_ospf.platform.socket_backend import SocketBackend

logger = logging.getLogger("mini_ospf.transport.sender")


class PacketSender:
    """Dispatches serialized OSPF packets across socket backends."""

    def __init__(self, sockets: dict[str, SocketBackend]) -> None:
        self.sockets = sockets  # interface_name -> SocketBackend

    def send_packet(
        self,
        raw_data: bytes,
        interface_name: str,
        dest_ip: str | None = None,
        dest_port: int | None = None,
    ) -> bool:
        backend = self.sockets.get(interface_name)
        if backend is None:
            logger.warning("No socket registered for interface %s", interface_name)
            return False

        target_ip = dest_ip if dest_ip is not None else "224.0.0.5"
        try:
            backend.send(raw_data, target_ip, dest_port)
            return True
        except Exception as e:
            logger.error("Failed to send packet on interface %s to %s: %s", interface_name, target_ip, e)
            return False
