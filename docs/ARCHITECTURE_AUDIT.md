# Mini-OSPF Architecture & Codebase Audit

**Date:** 2026-09-27  
**Auditor:** Senior Network-Protocol Engineer & Python Systems Architect  
**Repository:** `Mini-OSPF-Routing-Protocol`

---

## 1. Executive Summary

The existing repository is a high-level educational prototype / discrete-event script (`mini-ospf.py`) that models topology discovery and Dijkstra shortest-path calculations in memory. While it succeeds as a simplified computer science demonstration of link-state flooding and path reconstruction, it lacks the architecture, protocol state machines, packet formats, wire-level I/O, operating system integration, and observability of a real routing daemon.

This audit details the current state, identifies exact gaps against RFC 2328 (OSPFv2) and production routing control planes, and outlines an incremental refactoring plan to build a clean, typed, modular Python routing daemon and reproducible Linux network namespace lab.

---

## 2. Current Architecture & Code Inspection

### 2.1 File & Directory Layout
```text
Mini-OSPF-Routing-Protocol/
├── README.md           (3 lines - project statement)
├── mini-ospf.py        (315 lines - single monolith simulation)
└── topology.json       (12 lines - 5-node test topology)
```

### 2.2 Component Analysis

| Component | Current Implementation in `mini-ospf.py` | Production Reality / RFC 2328 Standard |
| :--- | :--- | :--- |
| **Runtime & Config** | Flat script with CLI `argparse` loading a centralized JSON topology file. | Independent daemon process per router loaded from dedicated YAML/TOML config with typed models and startup validation. |
| **Packet Handling** | No wire packets. In-memory Python `LSA` object instances passed across a global deque. | Binary wire-format serialization & parsing (`struct`, `memoryview`) of OSPF Headers, Hello, DBD, LSR, LSU, LSAck with Fletcher-16 / 1's complement checksums. |
| **Neighbor State** | Non-existent. Router assumes all neighbors in topology are permanently reachable and trusted. | Explicit 8-state Neighbor FSM (`DOWN`, `ATTEMPT`, `INIT`, `2-WAY`, `EXSTART`, `EXCHANGE`, `LOADING`, `FULL`) with deterministic event transitions and dead timers. |
| **Link State DB** | Simple dict `origin -> LSA`. Overwritten purely on `seq <= prev_seq`. | Structured database indexed by `(LSA_type, LinkStateID, AdvRouter)`, supporting sequence number rollover, aging, MaxAge flushing, checksum validation, and flooding queues. |
| **Graph & SPF** | Undirected graph constructed from LSA links; basic Dijkstra with `heapq` finding single next-hop via linear path backtracking. | SPF computing Shortest Path Tree (SPT) from Root, tracking intra-area router/network links, multi-interface next-hops, ECMP branches, and throttled SPF schedulers. |
| **RIB & FIB** | Local forwarding dict `dest_router_id -> (next_hop, cost)`. No IP prefixes or netmasks. | Routing Information Base (RIB) with IP prefix/len, metric, administrative distance, next-hop interfaces, longest-prefix match (LPM), and Linux Netlink FIB installer. |
| **Linux Networking** | None. Simulated queue with `time.sleep()`. | Real socket I/O (IP protocol 89 / UDP test harness / Multicast 224.0.0.5), Netlink (`pyroute2` / kernel sockets) for interface tracking and route installation. |
| **Observability** | `print()` statements. | Structured JSON/key-value logging, atomic metrics counters, and Unix domain socket / HTTP read-only management endpoints. |
| **Testing** | Hardcoded demo scenario in `__main__`. | Comprehensive pytest suite: unit tests, fuzz tests, integration tests, and multi-namespace Linux routing labs. |

---

## 3. What Already Works

1. **Topology Graph & Adjacency Representation**:
   - `Topology` class cleanly models bidirectional links and edge weights.
2. **Shortest Path Computation**:
   - `Router.run_dijkstra()` accurately implements Dijkstra's algorithm using a min-heap (`heapq`) and produces minimum-cost reachability on simulated graphs.
3. **Basic Path Backtracking**:
   - Correctly determines the immediate next-hop neighbor from `prev` pointers.
4. **Basic In-Memory Flooding & Dynamic Convergence**:
   - Demonstrates how link metric updates or link removals trigger re-flooding and table re-computation across simulated nodes.

---

## 4. What Is Incorrect & Problematic

1. **Symmetric Adjacency Assumption (`mini-ospf.py:132`)**:
   - `graph[neigh][origin] = cost` forces bidirectional symmetry even if the remote router has not advertised the reverse link. In real OSPF, a link is only valid in the SPF graph if the adjacency is confirmed bidirectional in the LSDB.
2. **Missing Router ID vs IP Prefix Distinction**:
   - The graph treats node names (`R1`, `R2`) as forwarding destinations. Real routers route IP prefixes (`10.0.1.0/24`) attached to router nodes.
3. **Monotonic Sequence Number without Wrap/Rules**:
   - Sequence number is a raw integer starting at 0 without signed 32-bit linear space (`0x80000001` to `0x7FFFFFFF`) or rollover handling.
4. **Direct Reference to Global Simulator Topology**:
   - `Router` queries `self.sim.topology.neighbors(self.name)` directly to decide what to advertise, bypassing real interface states.
5. **No Concurrency Safety or Event Loop**:
   - Relies on synchronous BFS queue drains (`process_delivery_queue`) mixed with blocking `time.sleep`.

---

## 5. What Is Missing

1. **OSPF Protocol Engine**:
   - Binary OSPFv2 packet encoder/decoder (Header, Hello, DBD, LSR, LSU, LSAck).
   - Standard Fletcher checksum calculation and verification.
2. **RFC 2328 Neighbor State Machine (FSM)**:
   - Explicit state transitions, 2-Way election / adjacency formation, Hello timers, Inactivity (Dead) timers.
3. **Link State Database Subsystem**:
   - Typed LSA structures (Router-LSA Type 1, Network-LSA Type 2, Summary-LSA Type 3/4, AS-External Type 5).
   - LSA age tracking (incrementing age, MaxAge 3600s, DoNotAge).
   - Database Synchronization (DBD exchange, Request list, Retransmission list).
4. **Enterprise-Grade SPF & RIB**:
   - SPF scheduler with exponential backoff timers (SPF throttling: init_delay, hold_time, max_delay).
   - Equal-Cost Multi-Path (ECMP) next-hop tracking.
   - RIB management with Longest Prefix Match (LPM) and route replacement.
5. **Linux Networking Platform**:
   - Real Linux Netlink interface event listener (detecting interface UP/DOWN, IP assignment).
   - Linux Kernel FIB Route Installer (`rtnetlink` / Netlink sockets) alongside Mock Route Installer.
   - Raw socket / UDP transport with multicast `224.0.0.5` (AllSPFRouters) and `224.0.0.6` (AllDRouters).
6. **Management & Lab Automation**:
   - Unix socket IPC management server and `mini-ospf` CLI with table formatting and `--json` support.
   - Linux network namespace (`ip netns`) lab automation scripts for 4-node and 5-node dynamic test topologies.
   - Comprehensive test harness: unit tests, fuzz tests, integration tests, performance benchmarks.

---

## 6. Production Gaps (Honest Assessment)

To maintain technical honesty:
- **Python Overhead**: A Python control plane is suitable for learning, lab testbeds, and research, but cannot achieve the sub-millisecond convergence of C/Rust routing stacks (such as FRR or BIRD) managing hundreds of thousands of BGP/OSPF routes.
- **Hardware Data Plane**: This project integrates with the Linux Kernel FIB (`netlink`). It does not program ASIC hardware forwarding tables (e.g., Broadcom SDK, SwitchDev, SAI).
- **Multi-Area & Virtual Links**: Initial production core focuses on single Area (Backbone 0.0.0.0) broadcast / point-to-point links before expanding to multi-area border routing (ABR/ASBR).

---

## 7. Target Architecture & Refactoring Plan

We will refactor the codebase into a clean, modern Python 3.12+ package:

```text
src/mini_ospf/
├── app/              # Daemon entry point, lifecycle, signal handling
├── protocol/         # Wire packet binary parsing, encoding, checksums, headers
├── ospf/             # Neighbor FSM, Hello, DBD, LSU, LSAck, Flooding engine
├── lsdb/             # LSA dataclasses, Database, Aging timer, Synchronization
├── spf/              # Graph builder, Dijkstra, ECMP, Next-Hop, SPF Scheduler
├── routing/          # RIB, IP Route, Longest Prefix Match, Route Policy
├── platform/         # Linux Netlink, Interface monitor, Kernel Route Installer
├── transport/        # Asyncio UDP/Raw socket senders/receivers, Multicast
├── config/           # YAML/TOML configuration models (pydantic/dataclasses) & validation
├── cli/              # Operator CLI tool (show neighbors, lsdb, routes, spf)
├── api/              # Local IPC Unix socket / JSON API server
├── observability/    # Structured logging, Prometheus-style metrics, Health checks
└── security/         # Malformed packet validation, rate limiting, resource limits
```

### Phased Execution Steps:
1. **Repository Setup**: `pyproject.toml`, dev environment, modern layout.
2. **Protocol & Binary Packet Engine**: Exact binary struct definitions, Fletcher checksum, wire parsing & fuzz validation.
3. **LSDB & LSA Model**: Typed LSA structures, sequence number math, LSA aging and database operations.
4. **Neighbor FSM Engine**: Deterministic FSM with states, timers, and transitions.
5. **SPF & Graph Engine**: Dijkstra with deterministic tie-breaking, ECMP, next-hop calculation, and SPF debouncing.
6. **RIB Subsystem**: Prefix table, LPM, route candidate selection.
7. **Platform & Kernel Route Installer**: Linux Netlink FIB installer and mock test installer.
8. **Transport & Asyncio Daemon**: Sockets, interface watcher, timer loop, local IPC socket.
9. **CLI & API**: CLI commands (`mini-ospf show ...`) with rich/text and JSON output.
10. **Observability & Metrics**: Structured logger, performance metrics.
11. **Comprehensive Tests & Benchmarks**: Unit, integration, fuzzing, and benchmark suites.
12. **Linux Network Namespace Lab**: Automated scripts (`create_topology.sh`, `fail_link.sh`, etc.) for real multi-router testing.
13. **Comprehensive Documentation**: Complete documentation suite and production readiness matrix.
