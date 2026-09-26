# Mini-OSPF Security Architecture & Hardening

## 1. Defensive Design Principles

1. **Defensive Ingestion**: No packet data is processed by business logic without passing IP checksum and header structure validation.
2. **Deterministic State Transitions**: State transitions are strictly controlled via `NeighborFSM` to prevent sequence injection attacks.
3. **Privilege Separation**: Route installation requires root/CAP_NET_ADMIN privileges in Linux, while the API server and parser operate purely in user space.
4. **No Dynamic Code Execution**: No `eval`, `exec`, or unsafe YAML loading (`yaml.safe_load` is used exclusively).

---

## 2. Resource Limits & Guards

```python
@dataclass(slots=True)
class ResourceLimits:
    max_lsas_in_db: int = 10000
    max_neighbors_per_interface: int = 255
    max_packet_rate_per_sec: int = 500
    max_payload_bytes: int = 65535
```

---

## 3. Cryptographic Authentication Readiness

The OSPF header models standard authentication types (`AuthType.NULL`, `AuthType.SIMPLE_PASSWORD`, `AuthType.CRYPTOGRAPHIC`). Future cryptographic extensions (HMAC-MD5/SHA-256) plug directly into `mini_ospf.protocol.validation`.
