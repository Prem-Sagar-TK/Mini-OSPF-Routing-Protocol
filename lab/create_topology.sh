#!/usr/bin/env bash
# ==============================================================================
# Linux Network Namespace Topology Setup for Mini-OSPF
#
# Topology (Diamond 4-Router Network):
#
#            R1 (1.1.1.1)
#           /  \
#  veth12  /    \  veth13
#         /      \
#   R2 (2.2.2.2)  R3 (3.3.3.3)
#         \      /
#  veth24  \    /  veth34
#           \  /
#            R4 (4.4.4.4)
#
# Subnets:
#   R1-R2: 10.0.12.0/24 (R1: .1, R2: .2)
#   R1-R3: 10.0.13.0/24 (R1: .1, R3: .3)
#   R2-R4: 10.0.24.0/24 (R2: .2, R4: .4)
#   R3-R4: 10.0.34.0/24 (R3: .3, R4: .4)
# ==============================================================================

set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "[-] Error: This script requires root privileges (sudo)." >&2
    exit 1
fi

echo "[+] Creating network namespaces: r1, r2, r3, r4"
ip netns add r1
ip netns add r2
ip netns add r3
ip netns add r4

# Enable IP forwarding inside each namespace
for ns in r1 r2 r3 r4; do
    ip netns exec "$ns" sysctl -w net.ipv4.ip_forward=1 >/dev/null
    ip netns exec "$ns" ip link set lo up
done

echo "[+] Creating veth pairs and interconnecting namespaces"

# Link R1 <-> R2 (10.0.12.0/24)
ip link add veth12 type veth peer name veth21
ip link set veth12 netns r1
ip link set veth21 netns r2
ip netns exec r1 ip addr add 10.0.12.1/24 dev veth12
ip netns exec r2 ip addr add 10.0.12.2/24 dev veth21
ip netns exec r1 ip link set veth12 up
ip netns exec r2 ip link set veth21 up

# Link R1 <-> R3 (10.0.13.0/24)
ip link add veth13 type veth peer name veth31
ip link set veth13 netns r1
ip link set veth31 netns r3
ip netns exec r1 ip addr add 10.0.13.1/24 dev veth13
ip netns exec r3 ip addr add 10.0.13.3/24 dev veth31
ip netns exec r1 ip link set veth13 up
ip netns exec r3 ip link set veth31 up

# Link R2 <-> R4 (10.0.24.0/24)
ip link add veth24 type veth peer name veth42
ip link set veth24 netns r2
ip link set veth42 netns r4
ip netns exec r2 ip addr add 10.0.24.2/24 dev veth24
ip netns exec r4 ip addr add 10.0.24.4/24 dev veth42
ip netns exec r2 ip link set veth24 up
ip netns exec r4 ip link set veth42 up

# Link R3 <-> R4 (10.0.34.0/24)
ip link add veth34 type veth peer name veth43
ip link set veth34 netns r3
ip link set veth43 netns r4
ip netns exec r3 ip addr add 10.0.34.3/24 dev veth34
ip netns exec r4 ip addr add 10.0.34.4/24 dev veth43
ip netns exec r3 ip link set veth34 up
ip netns exec r4 ip link set veth43 up

echo "[+] Multi-router network topology successfully created!"
