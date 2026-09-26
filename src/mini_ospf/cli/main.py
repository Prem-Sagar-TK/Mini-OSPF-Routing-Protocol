"""
Mini-OSPF Operator CLI (mini-ospf).
"""

import argparse
import asyncio
import json
import sys
from typing import Any

from mini_ospf.config.loader import load_config_file
from mini_ospf.config.validator import ConfigValidationError


async def _query_api_server(command: str, sock_path: str = "/tmp/mini_ospf.sock", tcp_port: int = 8990) -> dict[str, Any]:
    """Send command to running daemon and receive JSON response."""
    open_unix = getattr(asyncio, "open_unix_connection", None)
    if open_unix is not None:
        try:
            reader, writer = await open_unix(path=sock_path)
        except (NotImplementedError, OSError, FileNotFoundError):
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", tcp_port)
            except OSError as e:
                return {"error": f"Failed to connect to mini-ospf daemon: {e}"}
    else:
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", tcp_port)
        except OSError as e:
            return {"error": f"Failed to connect to mini-ospf daemon: {e}"}

    writer.write(f"{command}\n".encode())
    await writer.drain()

    raw_resp = await reader.readline()
    writer.close()
    await writer.wait_closed()

    if not raw_resp:
        return {"error": "Empty response from daemon"}

    try:
        data = json.loads(raw_resp.decode("utf-8"))
        return data if isinstance(data, dict) else {"data": data}
    except Exception as e:
        return {"error": f"Invalid JSON from daemon: {e}", "raw": raw_resp.decode("utf-8")}


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        print("No entries found.")
        return

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    header_fmt = "  ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths, strict=False))
    sep_fmt = "  ".join("-" * w for w in col_widths)

    print(header_fmt)
    print(sep_fmt)
    for row in rows:
        print("  ".join(f"{str(val):<{w}}" for val, w in zip(row, col_widths, strict=False)))
    print()


def cmd_check_config(args: argparse.Namespace) -> int:
    try:
        cfg = load_config_file(args.config)
        print(f"OK: Configuration '{args.config}' is valid for router {cfg.router_id}.")
        return 0
    except ConfigValidationError as e:
        print(f"CONFIGURATION ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def cmd_show(args: argparse.Namespace) -> int:
    sub = args.show_cmd
    cmd_str = f"show {sub}"
    if hasattr(args, "prefix") and args.prefix:
        cmd_str += f" {args.prefix}"

    res = asyncio.run(_query_api_server(cmd_str, args.socket, args.port))

    if "error" in res:
        print(f"Error: {res['error']}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(res, indent=2))
        return 0

    match sub:
        case "interfaces":
            headers = ["NAME", "IP ADDRESS", "AREA", "STATE", "METRIC", "HELLO/DEAD", "DR"]
            rows = []
            ifaces = res.get("interfaces", [])
            if isinstance(ifaces, list):
                for item in ifaces:
                    if isinstance(item, dict):
                        rows.append([
                            str(item.get("name", "")),
                            str(item.get("cidr", "")),
                            str(item.get("area_id", "")),
                            "UP" if item.get("is_up") else "DOWN",
                            str(item.get("metric", "")),
                            f"{item.get('hello_interval')}/{item.get('dead_interval')}",
                            str(item.get("designated_router", "")),
                        ])
            print(f"Interfaces for router {res.get('router_id')}:")
            _print_table(headers, rows)

        case "neighbors":
            headers = ["NEIGHBOR ID", "IP ADDRESS", "INTERFACE", "STATE", "PRIORITY", "DEAD TIME (s)"]
            rows = []
            neighs = res.get("neighbors", [])
            if isinstance(neighs, list):
                for item in neighs:
                    if isinstance(item, dict):
                        rows.append([
                            str(item.get("router_id", "")),
                            str(item.get("ip_address", "")),
                            str(item.get("interface_name", "")),
                            str(item.get("state", "")),
                            str(item.get("priority", "")),
                            str(item.get("dead_time_remaining", "")),
                        ])
            print(f"Neighbors for router {res.get('router_id')}:")
            _print_table(headers, rows)

        case "lsdb":
            headers = ["TYPE", "LINK STATE ID", "ADV ROUTER", "AGE", "SEQ NUM", "CHECKSUM"]
            rows = []
            lsas = res.get("lsas", [])
            if isinstance(lsas, list):
                for item in lsas:
                    if isinstance(item, dict):
                        rows.append([
                            str(item.get("ls_type", "")),
                            str(item.get("link_state_id", "")),
                            str(item.get("advertising_router", "")),
                            str(item.get("ls_age", "")),
                            f"0x{item.get('ls_sequence_number', 0):08X}" if isinstance(item.get('ls_sequence_number'), int) else str(item.get('ls_sequence_number')),
                            f"0x{item.get('ls_checksum', 0):04X}" if isinstance(item.get('ls_checksum'), int) else str(item.get('ls_checksum')),
                        ])
            print(f"OSPF Link State Database (Area {res.get('area_id')}):")
            _print_table(headers, rows)

        case "routes":
            headers = ["PREFIX", "METRIC", "ADMIN DIST", "NEXT HOPS", "TYPE"]
            rows = []
            routes = res.get("routes", [])
            if isinstance(routes, list):
                for item in routes:
                    if isinstance(item, dict):
                        nh_list = item.get("next_hops", [])
                        nhops = ", ".join(str(x) for x in nh_list) if isinstance(nh_list, list) and nh_list else "direct"
                        rows.append([
                            str(item.get("destination", "")),
                            str(item.get("metric", "")),
                            str(item.get("admin_distance", "")),
                            nhops,
                            str(item.get("route_type", "")),
                        ])
            print(f"OSPF Routing Table for {res.get('router_id')}:")
            _print_table(headers, rows)

        case "spf":
            print(f"SPF Status for router {res.get('router_id')}:")
            print(f"  Total SPF Runs: {res.get('total_runs')}")
            print(f"  Last Run Duration: {res.get('last_duration_ms')} ms")
            print(f"  Avg Run Duration:  {res.get('avg_duration_ms')} ms")
            print()

        case "statistics":
            print(f"Statistics for router {res.get('router_id')}:")
            print(json.dumps(res, indent=2))

        case _:
            print(json.dumps(res, indent=2))

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="mini-ospf", description="Mini-OSPF CLI & Management Tool")
    parser.add_argument("--socket", default="/tmp/mini_ospf.sock", help="Unix socket path for daemon API")
    parser.add_argument("--port", type=int, default=8990, help="TCP port fallback for daemon API")
    parser.add_argument("--json", action="store_true", help="Format output as JSON")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # check-config
    p_check = subparsers.add_parser("check-config", help="Validate a YAML configuration file")
    p_check.add_argument("config", help="Path to configuration file")
    p_check.set_defaults(func=cmd_check_config)

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Run the Mini-OSPF routing daemon")
    p_daemon.add_argument("-c", "--config", required=True, help="Path to YAML configuration file")
    p_daemon.add_argument(
        "--simulate",
        action="store_true",
        default=False,
        help="Run with mock sockets (no real networking). Auto-enabled on Windows.",
    )

    def _run_daemon(args: argparse.Namespace) -> int:
        from mini_ospf.app.daemon import run_daemon_from_config
        return run_daemon_from_config(args.config, simulate=args.simulate)

    p_daemon.set_defaults(func=_run_daemon)

    # show
    p_show = subparsers.add_parser("show", help="Show routing and protocol state")
    show_sub = p_show.add_subparsers(dest="show_cmd", required=True)

    for item in ("interfaces", "neighbors", "lsdb", "routes", "spf", "statistics"):
        sp = show_sub.add_parser(item, help=f"Show OSPF {item}")
        if item == "routes":
            sp.add_argument("prefix", nargs="?", default=None, help="Optional IP prefix to filter")
        sp.set_defaults(func=cmd_show)

    args = parser.parse_args()
    code = args.func(args)
    sys.exit(code)


if __name__ == "__main__":
    main()
