# Mini-OSPF Configuration Guide

Mini-OSPF uses typed YAML (or JSON) configuration files. Configurations are validated against strict schema rules prior to daemon startup.

---

## 1. Example Configuration

```yaml
router:
  router_id: "1.1.1.1"

areas:
  - id: "0.0.0.0"
    type: "standard"

interfaces:
  - name: "eth1"
    ip_address: "10.0.12.1"
    netmask: "255.255.255.0"
    area: "0.0.0.0"
    hello_interval: 10
    dead_interval: 40
    metric: 10
    priority: 1
    udp_port: 8989
    type: "broadcast"

spf:
  init_delay_ms: 50
  hold_time_ms: 100
  max_delay_ms: 5000

logging:
  level: "INFO"
  format: "text" # "text" or "json"
  file: "/var/log/mini_ospf.log"

server:
  api_enabled: true
  unix_socket_path: "/tmp/mini_ospf.sock"
  http_port: 8990

install_kernel_routes: true
```

---

## 2. Configuration Field Reference

| Section | Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`router`** | `router_id` | IPv4 String | *Required* | 32-bit unique router identifier. |
| **`areas`** | `id` | IPv4 String | `"0.0.0.0"` | OSPF Area ID. |
| **`interfaces`** | `name` | String | *Required* | OS Interface identifier (e.g. `eth0`, `veth12`). |
| | `ip_address` | IPv4 String | *Required* | Interface IPv4 address. |
| | `netmask` | IPv4 String | `"255.255.255.0"` | Interface subnet mask. |
| | `hello_interval` | Integer | `10` | Frequency of outgoing Hello packets (seconds). |
| | `dead_interval` | Integer | `40` | Inactivity timer before declaring neighbor down (seconds). |
| | `metric` | Integer | `10` | Cost of sending packets over this interface (>= 1). |
| **`spf`** | `init_delay_ms` | Integer | `50` | Initial holdoff delay before first SPF run (ms). |
| | `hold_time_ms` | Integer | `100` | Minimum interval between consecutive SPF runs (ms). |
| | `max_delay_ms` | Integer | `5000` | Maximum holdoff delay cap (ms). |
| **`install_kernel_routes`**| `bool` | `false` | When true on Linux, installs routes into kernel FIB. |

---

## 3. Configuration Validation CLI

To check a configuration file without launching the daemon:

```bash
mini-ospf check-config configs/examples/router1.yaml
```
