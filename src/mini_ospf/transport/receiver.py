"""
Asyncio Packet Receiver and Dispatcher.

Uses asyncio.DatagramProtocol for cross-platform support (Windows + Linux).
On Linux the socket backend may also use add_reader via SocketBackend.
"""

import asyncio
import logging
import sys
from collections.abc import Callable
from typing import Any

from mini_ospf.platform.socket_backend import SocketBackend

logger = logging.getLogger("mini_ospf.transport.receiver")


class _OSPFDatagramProtocol(asyncio.DatagramProtocol):
    """asyncio DatagramProtocol adapter that feeds into the daemon's packet handler."""

    def __init__(
        self,
        on_packet_received: Callable[[bytes, str, str, int], None],
        ifname: str,
    ) -> None:
        self.on_packet_received = on_packet_received
        self.ifname = ifname
        self._transport: asyncio.BaseTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        src_ip, src_port = addr
        try:
            self.on_packet_received(data, self.ifname, src_ip, src_port)
        except Exception as e:
            logger.error("Error dispatching packet on %s from %s: %s", self.ifname, src_ip, e)

    def error_received(self, exc: Exception) -> None:
        logger.warning("Datagram error on interface %s: %s", self.ifname, exc)

    def connection_lost(self, exc: Exception | None) -> None:
        if exc:
            logger.debug("Connection lost on interface %s: %s", self.ifname, exc)


class PacketReceiver:
    """
    Registers asynchronous read callbacks with asyncio event loop for each active interface socket.

    Cross-platform: uses asyncio.DatagramProtocol on Windows and add_reader on Linux/macOS
    (falling back to DatagramProtocol if add_reader raises NotImplementedError).
    """

    def __init__(
        self,
        on_packet_received: Callable[[bytes, str, str, int], None],
    ) -> None:
        self.on_packet_received = on_packet_received
        self._registered_sockets: list[tuple[SocketBackend, str]] = []
        self._transports: list[asyncio.BaseTransport] = []

    def register_interface(self, backend: SocketBackend, ifname: str) -> None:
        sock = backend.sock
        if sock is None:
            sock = backend.open()

        loop = asyncio.get_running_loop()

        # On Windows, add_reader is not supported — use DatagramProtocol instead.
        if sys.platform == "win32":
            self._register_datagram_protocol(loop, backend, ifname)
        else:
            try:
                loop.add_reader(sock.fileno(), self._on_read_ready, sock, ifname)
                self._registered_sockets.append((backend, ifname))
                logger.debug("Registered add_reader for %s (fd=%d)", ifname, sock.fileno())
            except NotImplementedError:
                # Fallback for event loops that don't support add_reader (e.g. ProactorEventLoop)
                self._register_datagram_protocol(loop, backend, ifname)

    def _register_datagram_protocol(
        self, loop: asyncio.AbstractEventLoop, backend: SocketBackend, ifname: str
    ) -> None:
        """Register using asyncio DatagramProtocol (Windows-compatible)."""
        sock = backend.sock
        if sock is None:
            sock = backend.open()

        protocol = _OSPFDatagramProtocol(self.on_packet_received, ifname)

        # create_datagram_endpoint with existing socket
        async def _connect() -> None:
            transport, _ = await loop.create_datagram_endpoint(
                lambda: protocol,
                sock=sock,
            )
            self._transports.append(transport)

        loop.create_task(_connect())
        self._registered_sockets.append((backend, ifname))
        logger.debug("Registered DatagramProtocol for %s", ifname)

    def _on_read_ready(self, sock: Any, ifname: str) -> None:
        """Callback used by add_reader (Linux/macOS)."""
        try:
            raw_data, (src_ip, src_port) = sock.recvfrom(65535)
            self.on_packet_received(raw_data, ifname, src_ip, src_port)
        except Exception as e:
            logger.error("Error reading packet on interface %s: %s", ifname, e)

    def stop(self) -> None:
        # Close DatagramProtocol transports
        for transport in self._transports:
            try:
                transport.close()
            except Exception:
                pass
        self._transports.clear()

        # Remove add_reader callbacks (Linux/macOS)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        if sys.platform != "win32":
            for backend, _ifname in self._registered_sockets:
                if backend.sock:
                    try:
                        loop.remove_reader(backend.sock.fileno())
                    except Exception:
                        pass

        self._registered_sockets.clear()
