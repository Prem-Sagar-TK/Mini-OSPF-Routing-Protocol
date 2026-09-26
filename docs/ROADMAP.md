# Mini-OSPF Engineering Roadmap

## Milestone 1: Core Routing Daemon & Lab (Completed)
- [x] Modern Python 3.12+ package layout and `pyproject.toml`.
- [x] Wire-level binary serializer and zero-copy parser for OSPF packets and LSAs.
- [x] Fletcher-16 (RFC 2328 / RFC 905) and 16-bit 1's complement IP checksum implementations.
- [x] RFC 2328 8-state Neighbor FSM with deterministic action transitions.
- [x] Link State Database (LSDB) with sequence number math, aging, and MaxAge eviction.
- [x] Dijkstra SPT with deterministic tie-breaking, bidirectional validation, and ECMP next-hops.
- [x] Exponential backoff SPF throttling scheduler.
- [x] Routing Information Base (RIB) with Longest Prefix Match and diff computation.
- [x] Linux Kernel FIB installer and Mock installer.
- [x] Multi-router Linux network namespace lab automation.
- [x] Operator CLI (`mini-ospf show ...`) and local Unix domain socket API.
- [x] Unit, integration, fuzzing, and benchmark test suites.

---

## Milestone 2: Multi-Area & BFD Integration (Planned)
- [ ] Area Border Router (ABR) Summary-LSA generation and area border filtering.
- [ ] OSPF Point-to-Multipoint and NBMA interface support.
- [ ] BFD (RFC 5880) integration for sub-second failure detection.

---

## Milestone 3: Security & Interop (Future)
- [ ] RFC 2328 Cryptographic Authentication (HMAC-MD5 / HMAC-SHA256).
- [ ] RFC 3623 Graceful Restart.
- [ ] Cisco IOS-XE / FRRouting interoperability test harness.
