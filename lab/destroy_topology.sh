#!/usr/bin/env bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "[-] Error: This script requires root privileges (sudo)." >&2
    exit 1
fi

echo "[+] Tearing down network namespaces: r1, r2, r3, r4"
for ns in r1 r2 r3 r4; do
    if ip netns list | grep -qw "$ns"; then
        ip netns del "$ns"
        echo "[*] Removed namespace $ns"
    fi
done

echo "[+] Lab topology destroyed cleanly."
