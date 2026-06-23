"""Graph topology and domain-object construction for Fly-in."""

from src.parser import ParsedMapData
from src.ZoneHub import Connection, Zone


class Graph:
    """Own the instantiated zones and undirected connections of a map."""

    def __init__(self) -> None:
        """Create an empty graph ready to receive parsed map data."""
        self.zones: dict[str, Zone] = {}
        self.connections: list[Connection] = []
        self.start_zone: Zone | None = None
        self.end_zone: Zone | None = None

    def configure(self, parsed_data: ParsedMapData) -> None:
        """Build a complete graph from validated parser output."""
        self.reset()
        for hub_data in parsed_data["hubs"]:
            zone = Zone(hub_data)
            self.zones[zone.name] = zone

        for connection_data in parsed_data["connections"]:
            from_zone = self.zones[connection_data["from"]]
            to_zone = self.zones[connection_data["to"]]
            connection = Connection(
                connection_data,
                from_zone,
                to_zone,
            )
            self.connections.append(connection)

        self.start_zone = next(
            zone for zone in self.zones.values() if zone.is_start
        )
        self.end_zone = next(
            zone for zone in self.zones.values() if zone.is_end
        )

    def reset(self) -> None:
        """Clear this graph and the domain registries it owns."""
        self.zones.clear()
        self.connections.clear()
        self.start_zone = None
        self.end_zone = None
        Zone.reset()
        Connection.reset()

    def connection_between(self, first: Zone, second: Zone) -> Connection:
        """Return the connection joining two adjacent zones."""
        for connection in first.connections:
            if connection.other_zone(first) is second:
                return connection
        raise ValueError(
            f"No connection between '{first.name}' and '{second.name}'"
        )
