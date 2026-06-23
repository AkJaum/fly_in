"""Object-oriented command-line lifecycle for Fly-in."""

import sys
from collections.abc import Sequence
from pathlib import Path

from src.drone import Drone, MoveIntent
from src.graph import Graph
from src.parser import MapParser
from src.ZoneHub import Connection, Zone


class Simulation:
    """Configure and run a Fly-in simulation."""

    def __init__(
        self,
        map_file: str,
        output_file: str = "outputs.txt",
    ) -> None:
        """Create an unconfigured simulation for ``map_file``."""
        self.map_file = map_file
        self.output_file = Path(output_file)
        self.parser = MapParser(map_file)
        self.graph = Graph()
        self.drones: list[Drone] = []
        self.active_drones: list[Drone] = []
        self.turn_outputs: list[str] = []
        self.turn_number = 0
        self.nb_drones = 0
        self.is_configured = False

    @classmethod
    def from_arguments(cls, arguments: Sequence[str]) -> "Simulation":
        """Create a simulation from command-line arguments."""
        map_file = arguments[0] if arguments else "map.txt"
        return cls(map_file)

    def configure(self) -> None:
        """Parse the map and prepare every object required to run."""
        self._clear_configuration()
        parsed_data = self.parser.parse_file()
        self.graph.configure(parsed_data)
        self.nb_drones = parsed_data["nb_drones"]
        self.drones = [Drone(self.graph) for _ in range(self.nb_drones)]
        self.active_drones = list(self.drones)
        self.output_file.write_text("", encoding="utf-8")
        self.is_configured = True

    def start(self) -> None:
        """Run turns until every configured drone has been delivered."""
        if not self.is_configured:
            self.configure()
        while self.active_drones:
            turn_output = self.next_turn()
            if turn_output:
                print(turn_output)

    def next_turn(self) -> str:
        """Act with every active drone and return this turn's output line."""
        if not self.is_configured:
            self.configure()
        if not self.active_drones:
            return ""

        intents: list[MoveIntent] = []
        for drone in self.active_drones:
            intent = drone.act()
            if intent is not None:
                intents.append(intent)

        accepted_intents = self._resolve_movements(intents)
        movements: list[str] = []
        for intent in accepted_intents:
            self._commit_movement(intent)
            movements.append(self._format_movement(intent))

        self.active_drones = [
            drone
            for drone in self.active_drones
            if not drone.finished_traversal
        ]
        if not movements and self.active_drones:
            raise RuntimeError("Simulation deadlock: no drone can move")
        self.turn_number += 1
        output = " ".join(movements)
        self.turn_outputs.append(output)
        with self.output_file.open("a", encoding="utf-8") as history:
            history.write(f"{output}\n")
        return output

    def execute(self) -> int:
        """Configure and start, returning a process-compatible status code."""
        try:
            self.configure()
            self.start()
        except (OSError, RuntimeError, ValueError) as error:
            print(f"Error configuring simulation: {error}", file=sys.stderr)
            return 1
        return 0

    def _clear_configuration(self) -> None:
        """Discard prior state before attempting a fresh configuration."""
        self.nb_drones = 0
        self.is_configured = False
        self.drones.clear()
        self.active_drones.clear()
        self.turn_outputs.clear()
        self.turn_number = 0
        Drone.reset()
        self.graph.reset()

    def _resolve_movements(
        self,
        intents: list[MoveIntent],
    ) -> list[MoveIntent]:
        """Select simultaneous movements that respect all capacities."""
        mandatory_arrivals = [
            intent for intent in intents if intent.is_arrival
        ]
        candidates = [intent for intent in intents if not intent.is_arrival]
        accepted = mandatory_arrivals + self._respect_connection_capacities(
            candidates
        )

        while True:
            rejected_intent = self._find_zone_capacity_rejection(accepted)
            if rejected_intent is None:
                break
            accepted.remove(rejected_intent)

        accepted_set = set(accepted)
        return [intent for intent in intents if intent in accepted_set]

    def _respect_connection_capacities(
        self,
        intents: list[MoveIntent],
    ) -> list[MoveIntent]:
        """Limit new traversals to each connection's per-turn capacity."""
        accepted: list[MoveIntent] = []
        usage: dict[Connection, int] = {}
        for intent in intents:
            used_capacity = usage.get(intent.connection, 0)
            if used_capacity >= intent.connection.max_link_capacity:
                continue
            accepted.append(intent)
            usage[intent.connection] = used_capacity + 1
        return accepted

    def _find_zone_capacity_rejection(
        self,
        accepted: list[MoveIntent],
    ) -> MoveIntent | None:
        """Find one optional arrival that causes projected overcapacity."""
        for zone in self.graph.zones.values():
            if zone.is_start or zone.is_end:
                continue
            projected = self._projected_occupancy(zone, accepted)
            overflow = projected - zone.max_drones
            if overflow <= 0:
                continue

            optional_arrivals = [
                intent
                for intent in accepted
                if not intent.is_arrival and intent.destination is zone
            ]
            if not optional_arrivals:
                raise RuntimeError(
                    f"Reserved arrival exceeds capacity of zone '{zone.name}'"
                )
            return optional_arrivals[-1]
        return None

    def _projected_occupancy(
        self,
        zone: Zone,
        accepted: list[MoveIntent],
    ) -> int:
        """Calculate physical plus reserved occupancy after a turn."""
        reserved_arrivals = sum(
            drone.transit_destination is zone
            for drone in self.active_drones
        )
        departures = sum(intent.origin is zone for intent in accepted)
        immediate_arrivals = sum(
            not intent.is_arrival
            and intent.destination is zone
            and intent.destination.kind != "restricted"
            for intent in accepted
        )
        new_reservations = sum(
            not intent.is_arrival
            and intent.destination is zone
            and intent.destination.kind == "restricted"
            for intent in accepted
        )
        return (
            len(zone.drones_in)
            + reserved_arrivals
            - departures
            + immediate_arrivals
            + new_reservations
        )

    def _commit_movement(self, intent: MoveIntent) -> None:
        """Apply one movement selected by the simultaneous resolver."""
        if intent.is_arrival:
            intent.drone.complete_move(intent)
        elif intent.destination.kind == "restricted":
            intent.drone.enter_transit(intent)
        else:
            intent.drone.complete_move(intent)

    @staticmethod
    def _format_movement(intent: MoveIntent) -> str:
        """Format one accepted movement according to the subject."""
        if not intent.is_arrival and intent.destination.kind == "restricted":
            destination = intent.connection.name
        else:
            destination = intent.destination.name
        return f"{intent.drone.id}-{destination}"


if __name__ == "__main__":
    raise SystemExit(Simulation.from_arguments(sys.argv[1:]).execute())
