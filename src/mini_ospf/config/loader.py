"""
Configuration file loader supporting YAML and JSON with validation.
"""

import json
from pathlib import Path
from typing import Any

import yaml

from mini_ospf.config.models import (
    AreaConfig,
    DaemonConfig,
    InterfaceConfig,
    LoggingConfig,
    ServerConfig,
    SPFConfig,
)
from mini_ospf.config.validator import validate_config


def load_config_from_dict(data: dict[str, Any]) -> DaemonConfig:
    """Parse raw dictionary into typed DaemonConfig dataclass."""
    router_data = data.get("router", {})
    router_id = router_data.get("router_id", "1.1.1.1")

    areas = []
    for a in data.get("areas", [{"id": "0.0.0.0"}]):
        areas.append(AreaConfig(id=a.get("id", "0.0.0.0"), type=a.get("type", "standard")))

    interfaces = []
    for iface in data.get("interfaces", []):
        interfaces.append(
            InterfaceConfig(
                name=iface.get("name", "eth0"),
                ip_address=iface.get("ip_address", "10.0.0.1"),
                netmask=iface.get("netmask", "255.255.255.0"),
                area=iface.get("area", "0.0.0.0"),
                hello_interval=int(iface.get("hello_interval", 10)),
                dead_interval=int(iface.get("dead_interval", 40)),
                metric=int(iface.get("metric", 10)),
                priority=int(iface.get("priority", 1)),
                udp_port=int(iface.get("udp_port", 8989)),
                type=iface.get("type", "broadcast"),
            )
        )

    spf_data = data.get("spf", {})
    spf = SPFConfig(
        init_delay_ms=int(spf_data.get("init_delay_ms", 50)),
        hold_time_ms=int(spf_data.get("hold_time_ms", 100)),
        max_delay_ms=int(spf_data.get("max_delay_ms", 5000)),
    )

    log_data = data.get("logging", {})
    logging_cfg = LoggingConfig(
        level=log_data.get("level", "INFO"),
        format=log_data.get("format", "text"),
        file=log_data.get("file"),
    )

    srv_data = data.get("server", {})
    server = ServerConfig(
        api_enabled=bool(srv_data.get("api_enabled", True)),
        unix_socket_path=srv_data.get("unix_socket_path", "/tmp/mini_ospf.sock"),
        http_port=srv_data.get("http_port", 8080),
    )

    install_kernel = bool(data.get("install_kernel_routes", False))

    cfg = DaemonConfig(
        router_id=router_id,
        areas=areas,
        interfaces=interfaces,
        spf=spf,
        logging=logging_cfg,
        server=server,
        install_kernel_routes=install_kernel,
    )

    validate_config(cfg)
    return cfg


def load_config_file(path_str: str | Path) -> DaemonConfig:
    """Load and validate configuration from YAML or JSON file."""
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(content)
    elif path.suffix.lower() == ".json":
        data = json.loads(content)
    else:
        # Try YAML parser by default
        data = yaml.safe_load(content)

    if not isinstance(data, dict):
        raise ValueError("Root configuration document must be a dictionary")

    return load_config_from_dict(data)
