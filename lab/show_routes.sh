#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_EXEC="${PROJECT_DIR}/.venv/bin/python"
if [ ! -f "$PYTHON_EXEC" ]; then
    PYTHON_EXEC="python3"
fi

echo "=================================================================="
echo "                  MINI-OSPF ROUTING LAB STATUS"
echo "=================================================================="

for r in 1 2 3 4; do
    echo "------------------ Router R$r (Namespace r$r) ------------------"
    echo "[Kernel FIB Routes]:"
    ip netns exec "r$r" ip route show proto ospf || true
    echo ""
    echo "[Mini-OSPF Neighbors]:"
    ip netns exec "r$r" "$PYTHON_EXEC" -m mini_ospf.cli.main --socket "/tmp/mini_ospf_r${r}.sock" show neighbors || true
    echo ""
    echo "[Mini-OSPF Routes]:"
    ip netns exec "r$r" "$PYTHON_EXEC" -m mini_ospf.cli.main --socket "/tmp/mini_ospf_r${r}.sock" show routes || true
    echo ""
done
