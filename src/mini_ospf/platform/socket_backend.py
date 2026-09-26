"""
Socket Backend abstractions for UDP multicast encapsulation and raw IP protocol 89.
"""

import logging
import socket
import struct

logger = logging.getLogger("mini_ospf.platform.socket")


class SocketBackend:
    """
    Manages socket bindings, multicast group memberships, and raw/UDP transmission.
    """

    def __init__(
        self,
        interface_name: str,
        bind_ip: str,
        port: int = 8989,
        use_raw_ip: bool = False,
    ) -> None:
        self.interface_name = interface_name
        self.bind_ip = bind_ip
        self.port = port
        self.use_raw_ip = use_raw_ip
        self.sock: socket.socket | None = None

    def open(self) -> socket.socket:
        """Create and bind socket with SO_REUSEADDR and multicast options."""
        if self.use_raw_ip:
            # Requires root / CAP_NET_RAW
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, 89)
            self.sock.bind((self.bind_ip, 0))
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind to port
            try:
                self.sock.bind(("", self.port))
            except OSError:
                self.sock.bind((self.bind_ip, self.port))

            # Join 224.0.0.5 AllSPFRouters multicast group if on non-loopback
            try:
                mreq = struct.pack("4s4s", socket.inet_aton("224.0.0.5"), socket.inet_aton(self.bind_ip))
                self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            except OSError as e:
                logger.debug("Could not join 224.0.0.5 multicast group on %s: %s", self.bind_ip, e)

        self.sock.setblocking(False)
        return self.sock

    def send(self, data: bytes, target_ip: str, target_port: int | None = None) -> int:
        """Send packet bytes to destination IP."""
        if self.sock is None:
            raise RuntimeError("Socket is not open")

        port = target_port if target_port is not None else self.port
        if self.use_raw_ip:
            return self.sock.sendto(data, (target_ip, 0))
        else:
            return self.sock.sendto(data, (target_ip, port))

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
