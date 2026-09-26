# Mini-OSPF Operations & Operator CLI Guide

## 1. Running the Daemon

Launch the daemon with a specified configuration file:

```bash
# Using installed entrypoint
mini-ospf daemon -c configs/examples/router1.yaml

# Or using Python module
python -m mini_ospf.app.daemon configs/examples/router1.yaml
```

---

## 2. Operator CLI Inspection Commands

The `mini-ospf show` commands communicate with the running daemon via the local Unix domain socket (or fallback TCP port):

### 2.1 Show Interfaces
```bash
mini-ospf show interfaces
```
Output:
```text
Interfaces for router 1.1.1.1:
NAME  IP ADDRESS    AREA     STATE  METRIC  HELLO/DEAD  DR
----------------------------------------------------------
eth1  10.0.12.1/24  0.0.0.0  UP     10      10/40       0.0.0.0
eth2  10.0.13.1/24  0.0.0.0  UP     10      10/40       0.0.0.0
```

### 2.2 Show Neighbors
```bash
mini-ospf show neighbors
```
Output:
```text
Neighbors for router 1.1.1.1:
NEIGHBOR ID  IP ADDRESS  INTERFACE  STATE  PRIORITY  DEAD TIME (s)
------------------------------------------------------------------
2.2.2.2      10.0.12.2   eth1       FULL   1         36
3.3.3.3      10.0.13.3   eth2       FULL   1         38
```

### 2.3 Show Link State Database (LSDB)
```bash
mini-ospf show lsdb
```
Output:
```text
OSPF Link State Database (Area 0.0.0.0):
TYPE    LINK STATE ID  ADV ROUTER  AGE  SEQ NUM     CHECKSUM
------------------------------------------------------------
ROUTER  1.1.1.1        1.1.1.1     12   0x80000003  0x4A12
ROUTER  2.2.2.2        2.2.2.2     18   0x80000002  0x3F89
ROUTER  3.3.3.3        3.3.3.3     15   0x80000002  0x51C4
ROUTER  4.4.4.4        4.4.4.4     8    0x80000002  0x228B
```

### 2.4 Show Routing Table (RIB)
```bash
mini-ospf show routes
```
Output:
```text
OSPF Routing Table for 1.1.1.1:
PREFIX         METRIC  ADMIN DIST  NEXT HOPS                      TYPE
----------------------------------------------------------------------------
4.4.4.4/32     20      110         via 10.0.12.2 dev eth1         INTRA_AREA
10.0.24.0/24   20      110         via 10.0.12.2 dev eth1         INTRA_AREA
10.0.34.0/24   20      110         via 10.0.13.3 dev eth2         INTRA_AREA
```

### 2.5 JSON Output for Telemetry & Automation
Add `--json` to any command:
```bash
mini-ospf --json show routes
```
