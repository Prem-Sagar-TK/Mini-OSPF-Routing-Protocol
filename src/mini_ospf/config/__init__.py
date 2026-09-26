"""
Configuration loading and validation subsystem.
"""

from mini_ospf.config.loader import load_config_file, load_config_from_dict
from mini_ospf.config.models import (
    AreaConfig,
    DaemonConfig,
    InterfaceConfig,
    LoggingConfig,
    ServerConfig,
    SPFConfig,
)
from mini_ospf.config.validator import ConfigValidationError, validate_config

__all__ = [
    "AreaConfig",
    "ConfigValidationError",
    "DaemonConfig",
    "InterfaceConfig",
    "LoggingConfig",
    "SPFConfig",
    "ServerConfig",
    "load_config_file",
    "load_config_from_dict",
    "validate_config",
]
