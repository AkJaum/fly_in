"""Graph topology and shortest-path helpers for Fly-in."""

import heapq
import itertools

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
        self._path_cache: dict[Zone, tuple[float, tuple[Zone, ...]]] = {}

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
        self._path_cache.clear()
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

    def shortest_cost_from(self, start: Zone) -> float:
        """Return the weighted shortest remaining cost from ``start``."""
        cost, _ = self._shortest_path_from(start)
        return cost

    def shortest_route_from(self, start: Zone) -> list[Zone]:
        """Return the weighted shortest route from ``start`` to the end."""
        _, route = self._shortest_path_from(start)
        return list(route)

    def reachable_neighbors(
        self,
        start: Zone,
    ) -> list[tuple[Zone, Connection, float]]:
        """List every neighbor that can still reach the end zone."""
        options: list[tuple[Zone, Connection, float]] = []
        for connection in start.connections:
            neighbor = connection.other_zone(start)
            if neighbor.kind == "blocked":
                continue
            try:
                cost = neighbor.weight + self.shortest_cost_from(neighbor)
            except ValueError:
                continue
            options.append((neighbor, connection, cost))
        options.sort(key=lambda option: (option[2], option[0].name))
        return options

    def _shortest_path_from(
        self,
        start: Zone,
    ) -> tuple[float, tuple[Zone, ...]]:
        """Cache and return the shortest path data from ``start``."""
        cached = self._path_cache.get(start)
        if cached is not None:
            return cached

        destination = self.end_zone
        if destination is None:
            raise ValueError("Cannot compute routes without an end zone")
        if start is destination:
            result: tuple[float, tuple[Zone, ...]] = (0.0, ())
            self._path_cache[start] = result
            return result

        distances: dict[Zone, float] = {start: 0.0}
        previous: dict[Zone, Zone] = {}
        sequence = itertools.count()
        pending: list[tuple[float, int, Zone]] = [
            (0.0, next(sequence), start)
        ]

        while pending:
            distance, _, zone = heapq.heappop(pending)
            if distance != distances.get(zone):
                continue
            if zone is destination:
                break

            for connection in zone.connections:
                neighbor = connection.other_zone(zone)
                if neighbor.kind == "blocked":
                    continue
                candidate = distance + neighbor.weight
                if candidate >= distances.get(neighbor, float("inf")):
                    continue
                distances[neighbor] = candidate
                previous[neighbor] = zone
                heapq.heappush(
                    pending,
                    (candidate, next(sequence), neighbor),
                )

        if destination not in distances:
            raise ValueError(
                f"No route available from zone '{start.name}'"
            )

        route = self._reconstruct_route(previous, start, destination)
        result = (distances[destination], tuple(route))
        self._path_cache[start] = result
        return result

    @staticmethod
    def _reconstruct_route(
        previous: dict[Zone, Zone],
        start: Zone,
        destination: Zone,
    ) -> list[Zone]:
        """Build a forward route excluding the starting zone."""
        route = [destination]
        cursor = destination
        while cursor is not start:
            cursor = previous[cursor]
            route.append(cursor)
        route.reverse()
        return route[1:]
