# Mini-OSPF Limitations & Production Gaps

To maintain engineering honesty, this document explicitly lists what is **not** equivalent to production carrier routing suites (such as Cisco IOS, Juniper Junos, FRRouting, or BIRD).

---

## 1. Production Gaps & Unsupported Features

1. **Multi-Area Border Routing (ABR / ASBR)**:
   - Current core daemon focuses on single Backbone Area (`0.0.0.0`) intra-area routing. Inter-area Summary-LSA generation across multiple area interfaces is not yet automated.
2. **Hardware Data Plane (ASIC / SwitchDev)**:
   - Mini-OSPF programs the Linux Kernel FIB (`netlink`). It does not program hardware ASIC tables (such as Broadcom SAI, Mellanox Spectrum, or Marvell Prestera).
3. **High Availability (Graceful Restart / NSR)**:
   - RFC 3623 OSPF Graceful Restart and Non-Stop Routing (NSR) state replication between active/standby control cards is not implemented.
4. **Sub-Second BFD (Bidirectional Forwarding Detection)**:
   - Relies on OSPF Hello/Dead timers (default 10s/40s, or 1s/3s fast hellos) rather than sub-millisecond hardware BFD offload.
5. **Full Cryptographic HMAC Authentication**:
   - RFC 2328 Simple Password and Null auth fields are parsed and modeled; HMAC-MD5 / HMAC-SHA256 cryptographic sequence checking is reserved for future milestones.
6. **Interoperability Testing**:
   - Tested in multi-router Linux network namespace topologies; has not yet undergone live testbed validation against physical Cisco/Juniper appliances.
