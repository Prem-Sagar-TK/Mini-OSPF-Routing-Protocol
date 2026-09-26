# Mini-OSPF Testing Strategy & Test Evidence

Mini-OSPF includes automated test suites covering unit logic, integration exchanges, fuzz resilience, performance benchmarks, and Linux network namespace environments.

---

## 1. Test Suite Categories

| Category | Location | Coverage |
| :--- | :--- | :--- |
| **Unit Tests** | `tests/unit/` | Checksum (IP & Fletcher-16), Packet serialization, LSDB & aging, Neighbor FSM transitions, Dijkstra SPT, ECMP, RIB LPM, and Config validation. |
| **Integration** | `tests/integration/` | End-to-end 2-node protocol exchange (Hello, DBD negotiation, LSDB flooding, and route installation). |
| **Fuzz Testing** | `tests/fuzz/` | Random byte streams, bitflips, header mutations, and byte-by-byte truncation boundaries. |
| **Performance** | `tests/performance/` | Scalability benchmarks across 10, 100, 1,000, and 10,000 node topologies, packet parser throughput, and LSDB insertion rates. |

---

## 2. Test Execution

Run the complete test suite:

```bash
pytest -v -s
```

### Actual Execution Evidence (33 / 33 Passed):

```text
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\GitProjects\Mini-OSPF-Routing-Protocol
configfile: pyproject.toml
testpaths: tests
plugins: asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False
collected 33 items

tests\fuzz\test_packet_fuzzing.py ...                                   [  9%]
tests\integration\test_protocol_exchange.py .                           [ 12%]
tests\performance\test_benchmarks.py [BENCHMARK] Dijkstra SPF (   10 nodes,    40 edges):    0.055 ms
[BENCHMARK] Dijkstra SPF (  100 nodes,   400 edges):    0.343 ms
[BENCHMARK] Dijkstra SPF ( 1000 nodes,  4000 edges):    4.246 ms
[BENCHMARK] Dijkstra SPF (10000 nodes, 40000 edges):   85.306 ms
.[BENCHMARK] Packet Parser: 5000 packets in 0.039s (128,444.6 packets/sec)
.[BENCHMARK] LSDB Insert: 2000 LSAs in 0.001s (2,021,427.1 LSAs/sec)
.[BENCHMARK] Route Installer: 5000 routes in 0.003s (1,858,252.5 routes/sec)
.                                                                       [ 24%]
tests\unit\test_checksum.py ....                                        [ 36%]
tests\unit\test_config.py ...                                           [ 45%]
tests\unit\test_lsdb.py ....                                            [ 57%]
tests\unit\test_neighbor_fsm.py ....                                    [ 69%]
tests\unit\test_packet_parser.py .....                                  [ 84%]
tests\unit\test_rib.py ..                                               [ 90%]
tests\unit\test_spf_dijkstra.py ...                                     [100%]

============================= 33 passed in 0.59s ==============================
```
