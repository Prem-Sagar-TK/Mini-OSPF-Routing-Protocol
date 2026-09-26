#!/usr/bin/env bash
set -euo pipefail

echo "[+] Stopping Mini-OSPF daemon instances"
pkill -f "mini_ospf.app.daemon" || true
echo "[+] All daemons stopped."
