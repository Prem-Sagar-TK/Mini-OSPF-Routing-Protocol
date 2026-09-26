"""
Configuration Validation Rules for Mini-OSPF.
"""

import ipaddress

from mini_ospf.config.models import DaemonConfig


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""


def _is_valid_ipv4(ip_str: str) -> bool:
    try:
        ipaddress.IPv4Address(ip_str)
        return True
    except ValueError:
        return False


def validate_config(config: DaemonConfig) -> None:
    """Run comprehensive validation on daemon configuration."""
    if not _is_valid_ipv4(config.router_id):
        raise ConfigValidationError(f"Invalid router_id '{config.router_id}': must be valid IPv4 address")

    if not config.areas:
        raise ConfigValidationError("At least one area must be configured")

    area_ids = set()
    for area in config.areas:
        if not _is_valid_ipv4(area.id):
            raise ConfigValidationError(f"Invalid area id '{area.id}'")
        area_ids.add(area.id)

    if not config.interfaces:
        raise ConfigValidationError("At least one interface must be configured")

    if_names = set()
    for iface in config.interfaces:
        if not iface.name:
            raise ConfigValidationError("Interface name cannot be empty")
        if iface.name in if_names:
            raise ConfigValidationError(f"Duplicate interface name '{iface.name}'")
        if_names.add(iface.name)

        if not _is_valid_ipv4(iface.ip_address):
            raise ConfigValidationError(f"Invalid interface ip_address '{iface.ip_address}' on {iface.name}")

        if not _is_valid_ipv4(iface.netmask):
            raise ConfigValidationError(f"Invalid interface netmask '{iface.netmask}' on {iface.name}")

        if iface.area not in area_ids:
            raise ConfigValidationError(
                f"Interface {iface.name} assigned to undefined area '{iface.area}'"
            )

        if iface.hello_interval <= 0:
            raise ConfigValidationError(f"hello_interval must be > 0 on {iface.name}")

        if iface.dead_interval <= iface.hello_interval:
            raise ConfigValidationError(
                f"dead_interval ({iface.dead_interval}s) must be greater than hello_interval ({iface.hello_interval}s) on {iface.name}"
            )

        if iface.metric <= 0:
            raise ConfigValidationError(f"Interface metric must be >= 1 on {iface.name}")
