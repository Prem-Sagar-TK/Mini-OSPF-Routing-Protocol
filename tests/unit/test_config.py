"""
Unit tests for configuration parsing and validation.
"""

import pytest

from mini_ospf.config.loader import load_config_from_dict
from mini_ospf.config.validator import ConfigValidationError


def test_valid_config_from_dict() -> None:
    data = {
        "router": {"router_id": "1.1.1.1"},
        "areas": [{"id": "0.0.0.0"}],
        "interfaces": [
            {
                "name": "eth0",
                "ip_address": "10.0.0.1",
                "netmask": "255.255.255.0",
                "area": "0.0.0.0",
                "hello_interval": 10,
                "dead_interval": 40,
                "metric": 10,
            }
        ],
    }
    cfg = load_config_from_dict(data)
    assert cfg.router_id == "1.1.1.1"
    assert len(cfg.interfaces) == 1
    assert cfg.interfaces[0].name == "eth0"


def test_invalid_router_id_fails() -> None:
    data = {
        "router": {"router_id": "not-an-ip"},
        "areas": [{"id": "0.0.0.0"}],
        "interfaces": [{"name": "eth0", "ip_address": "10.0.0.1", "netmask": "255.255.255.0"}],
    }
    with pytest.raises(ConfigValidationError, match="Invalid router_id"):
        load_config_from_dict(data)


def test_dead_interval_less_than_hello_fails() -> None:
    data = {
        "router": {"router_id": "1.1.1.1"},
        "areas": [{"id": "0.0.0.0"}],
        "interfaces": [
            {
                "name": "eth0",
                "ip_address": "10.0.0.1",
                "netmask": "255.255.255.0",
                "area": "0.0.0.0",
                "hello_interval": 40,
                "dead_interval": 10,  # Invalid: dead <= hello
            }
        ],
    }
    with pytest.raises(ConfigValidationError, match="dead_interval"):
        load_config_from_dict(data)
