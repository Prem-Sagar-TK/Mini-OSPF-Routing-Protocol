"""
Mini-OSPF Web Dashboard entry point.

Usage:
    python -m mini_ospf.webapp          # start on default 127.0.0.1:5000
    python -m mini_ospf.webapp --port 8080 --host 0.0.0.0
    python run_webapp.py
"""
import argparse
import sys
import os

# Add src to path so mini_ospf is importable when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from webapp.server import run_webapp

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mini-ospf-web",
        description="Mini-OSPF Network Dashboard",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Bind port (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()
    run_webapp(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()
