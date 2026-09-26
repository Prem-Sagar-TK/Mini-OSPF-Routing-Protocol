# Mini-OSPF Architecture Specification

## 1. System Overview

Mini-OSPF is an explicit, event-driven, modular Python 3.12+ routing control plane and reproducible Linux networking laboratory. The architecture is inspired by enterprise routing software (such as FRRouting and BIRD), strictly separating packet ingestion, validation, protocol finite state machines, link-state databases, shortest path calculation, and operating system FIB programming.

---

## 2. Packet-to-Route Processing Pipeline

The journey of an OSPF packet through the Mini-OSPF daemon is illustrated below:

```text
       Physical / Virtual Wire (Ethernet / Veth)
                        │
                        ▼
      [Socket Backend] (UDP Multicast 224.0.0.5 / Raw IP 89)
                        │
                        ▼
       [Packet Receiver] (Asyncio non-blocking reader)
                        │
                        ▼
       [Validation Layer] (Checksum, Version, Length, Auth)
                        │
                        ▼
        [Binary Parser] (struct / memoryview decoder)
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

## 3. Subsystem Breakdown

### 3.1 Platform & Sockets (`mini_ospf.platform`)
- **`SocketBackend`**: Encapsulates socket lifecycle, SO_REUSEADDR, and joining multicast group `224.0.0.5` (AllSPFRouters).
- **`LinuxRouteInstaller`**: Programs kernel FIB tables using netlink/iproute2.
- **`MockRouteInstaller`**: In-memory FIB simulator for hermetic unit and integration testing.

### 3.2 Protocol & Binary Parsing (`mini_ospf.protocol`)
- **Zero-Copy Parsing**: Utilizes `memoryview` and standard `struct` unpacking for zero unnecessary buffer copies.
- **Strict Verification**: Enforces RFC 1071 16-bit 1's complement packet header checksums and RFC 2328 / RFC 905 Fletcher-16 LSA checksums.
- **Malformed Packet Resilience**: Guaranteed non-crashing behavior under truncated or corrupted frames.

### 3.3 Neighbor Finite State Machine (`mini_ospf.ospf`)
- Explicit 8-state RFC 2328 Neighbor FSM (`DOWN`, `ATTEMPT`, `INIT`, `TWO_WAY`, `EXSTART`, `EXCHANGE`, `LOADING`, `FULL`).
- Master/Slave DBD negotiation and Sequence Number verification.
- Event-driven state transition callbacks and dead timer expiration supervision.

### 3.4 Link State Database (`mini_ospf.lsdb`)
- Structured in-memory storage indexed by `(LSAType, LinkStateID, AdvertisingRouter)`.
- RFC 2328 Section 12.1.6 sequence number comparisons (`is_newer_lsa`).
- LSA aging engine with MaxAge (3600s) eviction callbacks.
- Database Summary, Request, and Retransmission tracking.

### 3.5 Shortest Path First Engine (`mini_ospf.spf`)
- **Graph Builder**: Extracts directed router/transit edges with mandatory bidirectional link verification.
- **Dijkstra SPT**: Min-heap priority queue with deterministic tie-breaking.
- **ECMP Next-Hop Resolution**: Identifies all equal-cost next-hop interfaces/IPs.
- **SPF Throttling**: Exponential backoff scheduler (`init_delay`, `hold_time`, `max_delay`) to mitigate LSA burst storms.

### 3.6 Routing Information Base (`mini_ospf.routing`)
- Route dataclasses with prefix length, metric, administrative distance (110), and ECMP next-hops.
- Longest Prefix Match (`lookup_lpm`) using standard IPv4 network math.
- Incremental diff generation (`added`, `modified`, `deleted`) to minimize kernel FIB operations.
