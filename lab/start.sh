#!/usr/bin/env bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "[-] Error: This script requires root privileges (sudo)." >&2
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_EXEC="${PROJECT_DIR}/.venv/bin/python"

if [ ! -f "$PYTHON_EXEC" ]; then
    PYTHON_EXEC="python3"
fi

echo "[+] Starting Mini-OSPF routing daemons inside namespaces"

# Start R1
ip netns exec r1 "$PYTHON_EXEC" -m mini_ospf.app.daemon "${PROJECT_DIR}/configs/examples/router1.yaml" > /tmp/mini_ospf_r1.log 2>&1 &
echo "[*] Started R1 (PID $!)"

# Start R2
ip netns exec r2 "$PYTHON_EXEC" -m mini_ospf.app.daemon "${PROJECT_DIR}/configs/examples/router2.yaml" > /tmp/mini_ospf_r2.log 2>&1 &
echo "[*] Started R2 (PID $!)"

# Start R3
ip netns exec r3 "$PYTHON_EXEC" -m mini_ospf.app.daemon "${PROJECT_DIR}/configs/examples/router3.yaml" > /tmp/mini_ospf_r3.log 2>&1 &
echo "[*] Started R3 (PID $!)"

# Start R4
ip netns exec r4 "$PYTHON_EXEC" -m mini_ospf.app.daemon "${PROJECT_DIR}/configs/examples/router4.yaml" > /tmp/mini_ospf_r4.log 2>&1 &
echo "[*] Started R4 (PID $!)"

echo "[+] All daemons running in background. Logs saved in /tmp/mini_ospf_r*.log"
