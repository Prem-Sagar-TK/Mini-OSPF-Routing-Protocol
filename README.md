# Mini-OSPF: Python OSPFv2 Routing Daemon & Linux Network Lab

[![CI](https://github.com/Prem-Sagar-TK/Mini-OSPF-Routing-Protocol/actions/workflows/ci.yml/badge.svg)](https://github.com/Prem-Sagar-TK/Mini-OSPF-Routing-Protocol/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Type Checked](https://img.shields.io/badge/mypy-strict%20clean-brightgreen.svg)](https://mypy.readthedocs.io/)
[![Linted with Ruff](https://img.shields.io/badge/lint-ruff-black.svg)](https://github.com/astral-sh/ruff)

Mini-OSPF is a **serious Python 3.12+ OSPFv2 routing control plane and reproducible Linux networking laboratory**. It implements wire-format packet parsing, an explicit 8-state neighbor finite state machine, a typed Link State Database (LSDB) with aging, Dijkstra Shortest Path Tree (SPT) calculation with Equal-Cost Multi-Path (ECMP), a Routing Information Base (RIB) with Longest Prefix Match (LPM), and real Linux Kernel FIB integration via Netlink.

> **Engineering Honesty Disclaimer**: This is a production-oriented Python routing control plane designed for network research, protocol simulation, and hands-on routing laboratories. It is **not** a drop-in replacement for carrier-grade ASIC-backed operating systems (such as Cisco IOS-XR, Juniper Junos, or FRRouting). All benchmark results and capabilities documented below are derived from actual tests.

---

## 1. Complete Packet-to-Route Architecture

```text
       Physical / Virtual Wire (Ethernet / Veth)
                        │
                        ▼
      [Socket Backend] (UDP Multicast 224.0.0.5 / Raw IP 89)
                        │
                        ▼
       [Packet Receiver] (Asyncio non-blocking socket reader)
                        │
                        ▼
       [Validation Layer] (RFC 1071 Checksum, Version, Length)
                        │
                        ▼
        [Binary Parser] (Zero-copy memoryview / struct decoder)
                        │
                        ▼
      [Neighbor FSM] (Down -> Init -> 2-Way -> ExStart -> Full)
                        │
                        ▼
     [Link State Database (LSDB)] (LSA indexing, aging, sync)
                        │
                        ▼
   [SPF Engine (Dijkstra)] (SPT Tree, ECMP, Throttle scheduler)
                        │
                        ▼
    [Routing Information Base (RIB)] (Prefix table, LPM, Diffs)
                        │
                        ▼
    [Route Installer] (Linux Netlink / Kernel FIB / Mock)
```

---

## 2. Production-Readiness Matrix

| Capability | Status | Evidence |
| :--- | :--- | :--- |
| **Dijkstra SPF Engine** | **Implemented & Benchmarked** | Passes on 10 to 10,000 nodes (`tests/performance/test_benchmarks.py`); 10k nodes in 85.3 ms. |
| **LSDB Subsystem** | **Implemented & Tested** | Full LSA indexing, RFC 2328 sequence comparisons, and aging with MaxAge eviction (`tests/unit/test_lsdb.py`). |
| **Neighbor FSM** | **Implemented & Tested** | Explicit 8-state FSM with deterministic transitions (`tests/unit/test_neighbor_fsm.py`). |
| **Binary Packet Parsing** | **Implemented & Fuzzed** | Zero-copy `memoryview` parsing of all 5 packet types; 500+ fuzz mutations without crashes (`tests/fuzz/test_packet_fuzzing.py`). |
| **Fletcher-16 Checksum** | **Implemented & Tested** | RFC 2328 / RFC 905 compliant checksum calculation and verification (`tests/unit/test_checksum.py`). |
| **Linux FIB Integration** | **Implemented** | `LinuxRouteInstaller` via `ip route` / Netlink; `MockRouteInstaller` for hermetic testing. |
| **Network Lab Automation**| **Implemented** | Shell automation for 4-router Diamond topology in isolated Linux network namespaces (`lab/`). |
| **Operator CLI & API** | **Implemented & Tested** | `mini-ospf show (interfaces\|neighbors\|lsdb\|routes\|spf\|statistics)` over local Unix socket / TCP. |
| **SPF Throttling** | **Implemented & Tested** | Exponential backoff scheduler (`init_delay`, `hold_time`, `max_delay`) to mitigate LSA storms. |
| **Longest Prefix Match** | **Implemented & Tested** | IPv4 network prefix matching in RIB (`tests/unit/test_rib.py`). |
| **Multi-Area Routing** | *Roadmap / Experimental* | Single Backbone Area (0.0.0.0) supported; ABR logic planned for v0.2. |
| **Cryptographic Auth** | *Not Implemented Yet* | Header auth fields modeled; HMAC-SHA256 reserved for future milestone. |
| **Hardware ASIC Offload** | *Production Gap* | In-kernel Linux FIB only; no SwitchDev / Broadcom SDK data plane. |
| **Interoperability Testing**| *Untested Against Physical Hardware* | Validated in multi-instance Linux namespaces; physical Cisco/Juniper testbed pending. |

---

## 3. Measured Performance & Benchmarks

Measurements obtained directly on the test host with Python 3.14:

- **SPF Dijkstra (10 nodes, 40 edges)**: `0.055 ms`
- **SPF Dijkstra (100 nodes, 400 edges)**: `0.343 ms`
- **SPF Dijkstra (1,000 nodes, 4,000 edges)**: `4.246 ms`
- **SPF Dijkstra (10,000 nodes, 40,000 edges)**: `85.306 ms`
- **Packet Parser Throughput**: `128,444 packets/sec`
- **LSDB Insertion Throughput**: `2,021,427 LSAs/sec`
- **Route Installation (Mock FIB)**: `1,858,252 routes/sec`

---

## 4. Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Prem-Sagar-TK/Mini-OSPF-Routing-Protocol.git
cd Mini-OSPF-Routing-Protocol

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
pip install -e .[dev]
```

### Validate Configuration

```bash
mini-ospf check-config configs/examples/router1.yaml
```

### Run Automated Test Suite

```bash
pytest -v -s
```

---

## 5. Linux Network Namespace Multi-Router Lab

Mini-OSPF provides an automated 4-node diamond routing lab inside isolated Linux network namespaces:

```text
            R1 (1.1.1.1)
           /  \
  veth12  /    \  veth13
         /      \
   R2 (2.2.2.2)  R3 (3.3.3.3)
         \      /
  veth24  \    /  veth34
           \  /
            R4 (4.4.4.4)
```

### 1. Create Topology
```bash
sudo bash lab/create_topology.sh
```

### 2. Start Routing Daemons
```bash
sudo bash lab/start.sh
```

### 3. Inspect Converged Routes & Neighbors
```bash
sudo bash lab/show_routes.sh
```

### 4. Simulate Link Failure & Dynamic Convergence
```bash
# Bring down link R1 <-> R2
sudo bash lab/fail_link.sh r1-r2

# Observe automatic route re-convergence via R3
sudo bash lab/show_routes.sh

# Restore link
sudo bash lab/restore_link.sh r1-r2
```

### 5. Teardown Lab
```bash
sudo bash lab/stop.sh
sudo bash lab/destroy_topology.sh
```

---

## 6. Operator CLI Reference

Query the running daemon in human-readable table or `--json` formats:

```bash
# View active interfaces and DR state
mini-ospf show interfaces

# View neighbor FSM states (INIT, 2-WAY, EXCHANGE, FULL)
mini-ospf show neighbors

# View Link State Database entries
mini-ospf show lsdb

# View computed RIB routing table
mini-ospf show routes

# View SPF scheduler metrics
mini-ospf show spf

# View telemetry and health
mini-ospf --json show statistics
```

---

## 7. Documentation Index

- [Architecture Audit & Analysis](docs/ARCHITECTURE_AUDIT.md)
- [Architecture & Processing Pipeline](docs/ARCHITECTURE.md)
- [OSPF Protocol & RFC 2328 Compliance](docs/PROTOCOL.md)
- [Configuration Guide](docs/CONFIGURATION.md)
- [Operations & Operator CLI](docs/OPERATIONS.md)
- [Testing & Test Evidence](docs/TESTING.md)
- [Security Architecture](docs/SECURITY.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Performance & Benchmarks](docs/PERFORMANCE.md)
- [Limitations & Production Gaps](docs/LIMITATIONS.md)
- [Engineering Roadmap](docs/ROADMAP.md)

---

## 8. License

MIT License. See [LICENSE](LICENSE) for details.
