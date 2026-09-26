#!/usr/bin/env bash
# Restores physical link by bringing up veth interfaces
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "[-] Error: This script requires root privileges (sudo)." >&2
    exit 1
fi

LINK="${1:-r1-r2}"

case "$LINK" in
    "r1-r2")
        echo "[*] Restoring link R1 <-> R2 (veth12 / veth21 UP)"
        ip netns exec r1 ip link set veth12 up
        ip netns exec r2 ip link set veth21 up
        ;;
    "r1-r3")
        echo "[*] Restoring link R1 <-> R3 (veth13 / veth31 UP)"
        ip netns exec r1 ip link set veth13 up
        ip netns exec r3 ip link set veth31 up
        ;;
    "r2-r4")
        echo "[*] Restoring link R2 <-> R4 (veth24 / veth42 UP)"
        ip netns exec r2 ip link set veth24 up
        ip netns exec r4 ip link set veth42 up
        ;;
    "r3-r4")
        echo "[*] Restoring link R3 <-> R4 (veth34 / veth43 UP)"
        ip netns exec r3 ip link set veth34 up
        ip netns exec r4 ip link set veth43 up
        ;;
    *)
        echo "Usage: $0 [r1-r2|r1-r3|r2-r4|r3-r4]"
        exit 1
        ;;
esac

echo "[+] Link $LINK marked UP. OSPF Hello exchange and neighbor adjacency reforming..."
