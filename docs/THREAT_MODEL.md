# Mini-OSPF Threat Model & Security Analysis

## 1. Threat Surface Overview

Every network packet arriving at an interface socket is treated as **untrusted, hostile input**.

```text
       [External Network Packet]
                  │
                  ▼ (Threat: Flooding / Volumetric DoS)
         [Token Bucket Rate Limiter]
                  │
                  ▼ (Threat: Buffer Overflow / Huge Allocations)
        [Maximum Payload Size Limit (64KB)]
                  │
                  ▼ (Threat: Malformed Frame / Corrupted Bits)
         [Packet & Checksum Validation]
                  │
                  ▼ (Threat: State Exhaustion / Fake Neighbors)
           [Neighbor FSM Bounds]
                  │
                  ▼ (Threat: Poisoned LSAs / Subnet Hijacking)
          [LSDB & Bidirectional Check]
                  │
                  ▼ (Threat: SPF CPU Starvation)
         [Exponential Backoff Throttling]
                  │
                  ▼ (Threat: Privilege Escalation / FIB Tampering)
             [Kernel FIB Installer]
```

---

## 2. Threat Vector Analysis

| Threat Vector | Attack Scenario | Mitigation in Mini-OSPF |
| :--- | :--- | :--- |
| **Malformed Packet Attack** | Attacker crafts truncated or fuzz-mutated binary frames with invalid lengths or bad pointers. | Zero-copy `memoryview` boundary checks and `try/except (ValidationError, PacketParseError)` guards guarantee non-crashing behavior. |
| **Volumetric Packet Flood** | High-rate packet transmission targeting daemon CPU. | Token-bucket rate limiter (`RateLimiter`) drops frames exceeding interface capacity. |
| **SPF CPU Starvation** | Flapping link or rapid LSA injections forcing continuous Dijkstra computation. | `SPFScheduler` exponentially backs off SPF recalculations (`init_delay: 50ms`, `hold_time: 100ms`, `max_delay: 5000ms`). |
| **Asymmetric Route Injection** | Attacker advertises a link to a router without the target advertising a link back. | `build_topology_graph()` strictly enforces bidirectional adjacency verification before adding any edge to the SPF graph. |
| **Local API Abuse** | Non-privileged local users manipulating routing tables. | Management API is strictly **read-only** and bound to a protected Unix Domain Socket (`/tmp/mini_ospf.sock`) or loopback TCP. |
