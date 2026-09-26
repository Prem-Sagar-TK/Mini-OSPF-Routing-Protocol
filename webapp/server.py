"""
Flask Web Application Server for Mini-OSPF Dashboard.

Provides REST API endpoints and serves the dashboard frontend.
Runs the SimulatedNetwork in a background asyncio thread.
"""

import asyncio
import logging
import threading
import time
from typing import Any

from flask import Flask, jsonify, render_template, request, Response
from flask_cors import CORS

from mini_ospf.simulator.network import SimulatedNetwork

logger = logging.getLogger("mini_ospf.webapp")

# Global network instance and asyncio loop
_network: SimulatedNetwork | None = None
_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None


def _run_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Run asyncio event loop in a background thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _get_network() -> SimulatedNetwork:
    global _network
    if _network is None:
        raise RuntimeError("Network not initialized")
    return _network


def _run_coro_sync(coro: Any) -> Any:
    """Run a coroutine on the background event loop from a synchronous context."""
    global _loop
    if _loop is None:
        raise RuntimeError("Event loop not running")
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=10)


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    CORS(app)

    # ─── Pages ───────────────────────────────────────────────────────────────

    @app.route("/")
    def index() -> str:
        return render_template("index.html")

    # ─── API: Network Control ─────────────────────────────────────────────────

    @app.route("/api/network/start", methods=["POST"])
    def start_network() -> Response:
        global _network, _loop, _loop_thread
        if _network is not None and _loop is not None:
            return jsonify({"status": "already_running"})

        _network = SimulatedNetwork()
        _network.load_builtin_topology()

        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_run_event_loop, args=(_loop,), daemon=True)
        _loop_thread.start()

        _run_coro_sync(_network.start())
        return jsonify({"status": "started", "routers": list(_network.routers.keys())})

    @app.route("/api/network/stop", methods=["POST"])
    def stop_network() -> Response:
        global _network, _loop
        if _network is None:
            return jsonify({"status": "not_running"})
        _run_coro_sync(_network.stop())
        if _loop:
            _loop.call_soon_threadsafe(_loop.stop)
        _network = None
        _loop = None
        return jsonify({"status": "stopped"})

    @app.route("/api/network/reset", methods=["POST"])
    def reset_network() -> Response:
        global _network, _loop
        if _network is not None and _loop is not None:
            _run_coro_sync(_network.stop())
            _loop.call_soon_threadsafe(_loop.stop)

        _network = SimulatedNetwork()
        _network.load_builtin_topology()
        _loop = asyncio.new_event_loop()
        t = threading.Thread(target=_run_event_loop, args=(_loop,), daemon=True)
        t.start()
        _run_coro_sync(_network.start())
        return jsonify({"status": "reset", "routers": list(_network.routers.keys())})

    @app.route("/api/network/snapshot")
    def network_snapshot() -> Response:
        net = _get_network()
        return jsonify(net.snapshot())

    # ─── API: Link Control ────────────────────────────────────────────────────

    @app.route("/api/link/toggle", methods=["POST"])
    def toggle_link() -> Response:
        data = request.get_json(force=True)
        router_a = data.get("router_a", "")
        router_b = data.get("router_b", "")
        net = _get_network()
        success = net.toggle_link(router_a, router_b)
        link = net.bus.get_link(router_a, router_b)
        return jsonify({
            "success": success,
            "is_up": link.is_up if link else None,
            "router_a": router_a,
            "router_b": router_b,
        })

    @app.route("/api/link/loss", methods=["POST"])
    def set_link_loss() -> Response:
        data = request.get_json(force=True)
        router_a = data.get("router_a", "")
        router_b = data.get("router_b", "")
        loss = float(data.get("loss_percent", 0))
        net = _get_network()
        success = net.set_link_loss(router_a, router_b, loss)
        return jsonify({"success": success, "loss_percent": loss})

    # ─── API: Per-Router Queries ──────────────────────────────────────────────

    @app.route("/api/router/<router_id>/routes")
    def router_routes(router_id: str) -> Response:
        net = _get_network()
        node = net.routers.get(router_id)
        if node is None:
            return jsonify({"error": "Router not found"}), 404
        routes = [
            {
                "destination": r.destination,
                "metric": r.metric,
                "route_type": r.route_type.name,
                "next_hops": [str(nh) for nh in r.next_hops],
            }
            for r in node.daemon.rib.all_routes()
        ]
        return jsonify({"router_id": router_id, "routes": routes})

    @app.route("/api/router/<router_id>/lsdb")
    def router_lsdb(router_id: str) -> Response:
        net = _get_network()
        node = net.routers.get(router_id)
        if node is None:
            return jsonify({"error": "Router not found"}), 404
        lsas = [
            {
                "ls_type": lsa.header.ls_type.name,
                "link_state_id": lsa.header.link_state_id,
                "advertising_router": lsa.header.advertising_router,
                "ls_age": lsa.header.ls_age,
                "ls_sequence_number": lsa.header.ls_sequence_number,
            }
            for lsa in node.daemon.lsdb.all_lsas()
        ]
        return jsonify({"router_id": router_id, "lsdb": lsas})

    @app.route("/api/router/<router_id>/neighbors")
    def router_neighbors(router_id: str) -> Response:
        net = _get_network()
        node = net.routers.get(router_id)
        if node is None:
            return jsonify({"error": "Router not found"}), 404
        neighbors = [
            {
                "router_id": n.router_id,
                "ip_address": n.ip_address,
                "interface_name": n.interface_name,
                "state": n.state.name,
            }
            for n in node.daemon.neighbors.values()
        ]
        return jsonify({"router_id": router_id, "neighbors": neighbors})

    @app.route("/api/router/<router_id>/statistics")
    def router_statistics(router_id: str) -> Response:
        net = _get_network()
        node = net.routers.get(router_id)
        if node is None:
            return jsonify({"error": "Router not found"}), 404
        return jsonify({
            "router_id": router_id,
            "metrics": node.daemon.metrics.snapshot(),
            "health": node.daemon.health_checker.check(),
        })

    return app


def run_webapp(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    """Start the Flask web application."""
    app = create_app()
    print(f"\n{'='*55}")
    print(f"  Mini-OSPF Dashboard  ->  http://{host}:{port}")
    print(f"{'='*55}\n")
    app.run(host=host, port=port, debug=debug, use_reloader=False)
