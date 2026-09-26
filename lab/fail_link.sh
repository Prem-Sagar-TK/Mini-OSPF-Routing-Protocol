#!/usr/bin/env bash
# Simulates physical link failure by taking down veth interfaces
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "[-] Error: This script requires root privileges (sudo)." >&2
    exit 1
fi

LINK="${1:-r1-r2}"

case "$LINK" in
    "r1-r2")
        echo "[*] Failing link R1 <-> R2 (veth12 / veth21 DOWN)"
        ip netns exec r1 ip link set veth12 down
        ip netns exec r2 ip link set veth21 down
        ;;
    "r1-r3")
        echo "[*] Failing link R1 <-> R3 (veth13 / veth31 DOWN)"
        ip netns exec r1 ip link set veth13 down
        ip netns exec r3 ip link set veth31 down
        ;;
    "r2-r4")
        echo "[*] Failing link R2 <-> R4 (veth24 / veth42 DOWN)"
        ip netns exec r2 ip link set veth24 down
        ip netns exec r4 ip link set veth42 down
        ;;
    "r3-r4")
        echo "[*] Failing link R3 <-> R4 (veth34 / veth43 DOWN)"
        ip netns exec r3 ip link set veth34 down
        ip netns exec r4 ip link set veth43 down
        ;;
    *)
        echo "Usage: $0 [r1-r2|r1-r3|r2-r4|r3-r4]"
        exit 1
        ;;
esac

echo "[+] Link $LINK marked DOWN. OSPF dead timer and re-convergence in progress..."
