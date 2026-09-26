"""
Local Management API Server (Unix Domain Socket / TCP JSON-RPC).
"""

import asyncio
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger("mini_ospf.api.server")


class APIServer:
    """
    Asynchronous JSON-RPC / REST-like management server running over a Unix Domain Socket or TCP port.
    Provides read-only inspection endpoints for CLI and telemetry tools.
    """

    def __init__(
        self,
        get_state_callback: Callable[[str], dict[str, Any]],
        unix_socket_path: str = "/tmp/mini_ospf.sock",
        tcp_port: int | None = None,
    ) -> None:
        self.get_state_callback = get_state_callback
        self.unix_socket_path = unix_socket_path
        self.tcp_port = tcp_port
        self.server: asyncio.Server | None = None

    async def start(self) -> None:
        # Handle Unix domain socket
        sock_path = Path(self.unix_socket_path)
        if sock_path.exists():
            try:
                sock_path.unlink()
            except OSError:
                pass

        start_unix = getattr(asyncio, "start_unix_server", None)
        if start_unix is not None:
            try:
                self.server = await start_unix(self._handle_client, path=str(sock_path))
                logger.info("API server listening on Unix socket %s", self.unix_socket_path)
                return
            except (NotImplementedError, OSError) as e:
                logger.debug("Unix socket start failed: %s; falling back to TCP", e)

        port = self.tcp_port if self.tcp_port is not None else 8990
        self.server = await asyncio.start_server(
            self._handle_client, host="127.0.0.1", port=port
        )
        logger.info("API server listening on TCP 127.0.0.1:%d", port)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            line = await reader.readline()
            if not line:
                return

            req_str = line.decode("utf-8").strip()
            response_data = self.get_state_callback(req_str)
            response_json = json.dumps(response_data, default=str) + "\n"
            writer.write(response_json.encode("utf-8"))
            await writer.drain()
        except Exception as e:
            logger.error("Error handling API request: %s", e)
            err_json = json.dumps({"error": str(e)}) + "\n"
            writer.write(err_json.encode("utf-8"))
            await writer.drain()
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

        sock_path = Path(self.unix_socket_path)
        if sock_path.exists():
            try:
                sock_path.unlink()
            except OSError:
                pass
