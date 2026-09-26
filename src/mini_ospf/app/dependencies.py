"""
Dependency injection container for Mini-OSPF daemon.
"""

from dataclasses import dataclass

from mini_ospf.config.models import DaemonConfig
from mini_ospf.lsdb.database import LinkStateDatabase
from mini_ospf.observability.metrics import MetricsCollector
from mini_ospf.platform.interfaces import Interface
from mini_ospf.platform.route_installer import BaseRouteInstaller
from mini_ospf.routing.rib import RIB
from mini_ospf.security.limits import ResourceLimits


@dataclass(slots=True)
class DaemonDependencies:
    config: DaemonConfig
    lsdb: LinkStateDatabase
    rib: RIB
    route_installer: BaseRouteInstaller
    metrics: MetricsCollector
    limits: ResourceLimits
    interfaces: dict[str, Interface]
