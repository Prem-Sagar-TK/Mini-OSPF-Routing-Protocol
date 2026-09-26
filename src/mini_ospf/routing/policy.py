"""
Routing Policy and Administrative Distance definitions.
"""

from mini_ospf.routing.route import Route, RouteType

# Standard Administrative Distances
ADMIN_DISTANCE_CONNECTED: int = 0
ADMIN_DISTANCE_STATIC: int = 1
ADMIN_DISTANCE_OSPF_INTRA: int = 110
ADMIN_DISTANCE_OSPF_INTER: int = 110
ADMIN_DISTANCE_OSPF_EXTERNAL: int = 110
ADMIN_DISTANCE_RIP: int = 120
ADMIN_DISTANCE_BGP_EBGP: int = 20
ADMIN_DISTANCE_BGP_IBGP: int = 200


def assign_admin_distance(route: Route) -> None:
    """Assign default administrative distance based on route source / type."""
    match route.route_type:
        case RouteType.CONNECTED:
            route.admin_distance = ADMIN_DISTANCE_CONNECTED
        case RouteType.STATIC:
            route.admin_distance = ADMIN_DISTANCE_STATIC
        case RouteType.INTRA_AREA | RouteType.INTER_AREA:
            route.admin_distance = ADMIN_DISTANCE_OSPF_INTRA
        case RouteType.EXTERNAL_TYPE_1 | RouteType.EXTERNAL_TYPE_2:
            route.admin_distance = ADMIN_DISTANCE_OSPF_EXTERNAL
