"""
Configuration Models for Mini-OSPF Daemons.
"""

from dataclasses import dataclass, field


@dataclass(slots=True)
class InterfaceConfig:
    name: str
    ip_address: str
    netmask: str = "255.255.255.0"
    area: str = "0.0.0.0"
    hello_interval: int = 10
    dead_interval: int = 40
    metric: int = 10
    priority: int = 1
    udp_port: int = 8989
    type: str = "broadcast"  # broadcast, p2p, loopback


@dataclass(slots=True)
class AreaConfig:
    id: str = "0.0.0.0"
    type: str = "standard"  # standard, stub, nssa


@dataclass(slots=True)
class SPFConfig:
    init_delay_ms: int = 50
    hold_time_ms: int = 100
    max_delay_ms: int = 5000


@dataclass(slots=True)
class LoggingConfig:
    level: str = "INFO"
    format: str = "text"  # text or json
    file: str | None = None


@dataclass(slots=True)
class ServerConfig:
    api_enabled: bool = True
    unix_socket_path: str = "/tmp/mini_ospf.sock"
    http_port: int | None = 8080


@dataclass(slots=True)
class DaemonConfig:
    router_id: str
    areas: list[AreaConfig] = field(default_factory=lambda: [AreaConfig(id="0.0.0.0")])
    interfaces: list[InterfaceConfig] = field(default_factory=list)
    spf: SPFConfig = field(default_factory=SPFConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    install_kernel_routes: bool = False
