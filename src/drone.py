"""Drone entity and individual route traversal for Fly-in."""

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
        self.previous_zone: Zone | None = None
        self.route: list[Zone] = []
        self.finished_traversal = self.current_zone is graph.end_zone
        self.in_transit: Connection | None = None
        self.transit_destination: Zone | None = None
        self.wait_turns = 0
        graph.start_zone.drones_in.append(self)
        Drone._all_drones.append(self)

    def act(self) -> MoveIntent | None:
        """Calculate a route and propose this turn's movement."""
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
        self.route = self.path_finding()
        return self.move()

    def path_finding(self) -> list[Zone]:
        """Find the lowest-weight remaining route from the current zone."""
        if self.in_transit is not None:
            return self.route

        current_zone = self.current_zone
        if current_zone is None:
            raise RuntimeError("Drone has no zone outside of transit")
        if current_zone is self.graph.end_zone:
            self.finished_traversal = True
            self.route = []
            return self.route

        try:
            self.route = self.graph.shortest_route_from(current_zone)
        except ValueError as error:
            raise ValueError(f"No route available for {self.id}") from error
        return self.route

    def move(self) -> MoveIntent | None:
        """Create an intent for the next route step or transit arrival."""
        if self.finished_traversal:
            return None
        if self.current_zone is None:
            raise RuntimeError("Drone has no origin zone")
        if not self.route:
            return None

        next_zone = self.route[0]
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
        self.previous_zone = intent.origin
        intent.origin.drones_in.remove(self)
        intent.connection.drones_in.append(self)
        self.current_zone = None
        self.in_transit = intent.connection
        self.transit_destination = intent.destination
        self.route = []
        self.wait_turns = 0

    def complete_move(self, intent: MoveIntent) -> None:
        """Commit a normal move or mandatory transit arrival."""
        if intent.is_arrival:
            intent.connection.drones_in.remove(self)
            self.in_transit = None
            self.transit_destination = None
        elif intent.origin is not None:
            self.previous_zone = intent.origin
            intent.origin.drones_in.remove(self)

        self.current_zone = intent.destination
        intent.destination.drones_in.append(self)
        self.route = []
        self.wait_turns = 0
        if self.current_zone is self.graph.end_zone:
            self.finished_traversal = True

    def candidate_intents(self) -> list[MoveIntent]:
        """Return every neighbor move that still reaches the destination."""
        if self.finished_traversal:
            return []
        if self.in_transit is not None:
            destination = self.transit_destination
            if destination is None:
                raise RuntimeError("Drone transit has no destination")
            return [
                MoveIntent(
                    self,
                    None,
                    destination,
                    self.in_transit,
                    is_arrival=True,
                )
            ]
        if self.current_zone is None:
            raise RuntimeError("Drone has no origin zone")

        intents: list[MoveIntent] = []
        for neighbor, connection, _ in self.graph.reachable_neighbors(
            self.current_zone
        ):
            intents.append(
                MoveIntent(
                    self,
                    self.current_zone,
                    neighbor,
                    connection,
                )
            )
        return intents

    def mark_waiting(self) -> None:
        """Track consecutive turns where the drone could not move."""
        if not self.finished_traversal and self.in_transit is None:
            self.wait_turns += 1

    @classmethod
    def reset(cls) -> None:
        """Clear the drone registry and restart identifiers at D1."""
        cls._all_drones.clear()
        cls._next_identifier = 1
