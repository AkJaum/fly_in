"""Drone entity and individual route traversal for Fly-in."""

import heapq
import itertools
from dataclasses import dataclass

from src.graph import Graph
from src.ZoneHub import Connection, Zone


@dataclass(frozen=True)
class MoveIntent:
    """Describe a proposed move without mutating simulation state."""

    drone: "Drone"
    origin: Zone | None
    destination: Zone
    connection: Connection
    is_arrival: bool = False


class Drone:
    """Represent one drone travelling through a configured graph."""

    _all_drones: list["Drone"] = []
    _next_identifier = 1

    def __init__(self, graph: Graph) -> None:
        """Create a uniquely identified drone at the graph's start zone."""
        if graph.start_zone is None or graph.end_zone is None:
            raise ValueError(
                "Cannot create a drone from an unconfigured graph"
            )

        self.id = f"D{Drone._next_identifier}"
        Drone._next_identifier += 1
        self.graph = graph
        self.current_zone: Zone | None = graph.start_zone
        self.route: list[Zone] = []
        self.finished_traversal = self.current_zone is graph.end_zone
        self.in_transit: Connection | None = None
        self.transit_destination: Zone | None = None
        self._route_index = 0
        graph.start_zone.drones_in.append(self)
        Drone._all_drones.append(self)

    def act(self) -> MoveIntent | None:
        """Calculate a route and propose this turn's movement."""
        if self.finished_traversal:
            return None
        self.path_finding()
        return self.move()

    def path_finding(self) -> list[Zone]:
        """Find the lowest-weight remaining route with Dijkstra's algorithm."""
        if self.in_transit is not None:
            return self.route
        if self._route_index < len(self.route):
            return self.route

        destination = self.graph.end_zone
        if destination is None:
            raise ValueError("Cannot find a path without an end zone")
        current_zone = self.current_zone
        if current_zone is None:
            raise RuntimeError("Drone has no zone outside of transit")
        if current_zone is destination:
            self.finished_traversal = True
            self.route = []
            self._route_index = 0
            return self.route

        distances: dict[Zone, float] = {current_zone: 0.0}
        previous: dict[Zone, Zone] = {}
        sequence = itertools.count()
        pending: list[tuple[float, int, Zone]] = [
            (0.0, next(sequence), current_zone)
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
            raise ValueError(f"No route available for {self.id}")

        self.route = self._reconstruct_route(previous, destination)
        self._route_index = 0
        return self.route

    def move(self) -> MoveIntent | None:
        """Create an intent for the next route step or transit arrival."""
        if self.finished_traversal:
            return None

        if self.in_transit is not None:
            destination = self.transit_destination
            if destination is None:
                raise RuntimeError("Drone transit has no destination")
            return MoveIntent(
                self,
                None,
                destination,
                self.in_transit,
                is_arrival=True,
            )

        if self._route_index >= len(self.route):
            return None
        if self.current_zone is None:
            raise RuntimeError("Drone has no origin zone")

        next_zone = self.route[self._route_index]
        connection = self.graph.connection_between(
            self.current_zone,
            next_zone,
        )
        return MoveIntent(
            self,
            self.current_zone,
            next_zone,
            connection,
        )

    def enter_transit(self, intent: MoveIntent) -> None:
        """Leave the origin and occupy a restricted-zone connection."""
        if intent.origin is None:
            raise ValueError("A transit entry requires an origin zone")
        intent.origin.drones_in.remove(self)
        intent.connection.drones_in.append(self)
        self.current_zone = None
        self.in_transit = intent.connection
        self.transit_destination = intent.destination

    def complete_move(self, intent: MoveIntent) -> None:
        """Commit a normal move or mandatory transit arrival."""
        if intent.is_arrival:
            intent.connection.drones_in.remove(self)
            self.in_transit = None
            self.transit_destination = None
        elif intent.origin is not None:
            intent.origin.drones_in.remove(self)

        self._route_index += 1
        self.current_zone = intent.destination
        intent.destination.drones_in.append(self)
        if self.current_zone is self.graph.end_zone:
            self.finished_traversal = True

    def _reconstruct_route(
        self,
        previous: dict[Zone, Zone],
        destination: Zone,
    ) -> list[Zone]:
        """Build a forward route excluding the drone's current zone."""
        route = [destination]
        cursor = destination
        while cursor is not self.current_zone:
            cursor = previous[cursor]
            route.append(cursor)
        route.reverse()
        return route[1:]

    @classmethod
    def reset(cls) -> None:
        """Clear the drone registry and restart identifiers at D1."""
        cls._all_drones.clear()
        cls._next_identifier = 1
