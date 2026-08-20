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
        self.moved_drones_per_turn: list[int] = []
        self.drone_completion_turns: list[int] = []
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
        self._print_performance_metrics()

    def next_turn(self) -> str:
        """Act with every active drone and return this turn's output line."""
        if not self.is_configured:
            self.configure()
        if not self.active_drones:
            return ""

        accepted_intents = self._plan_turn()
        movements: list[str] = []
        for intent in accepted_intents:
            self._commit_movement(intent)
            movements.append(self._format_movement(intent))

        completed_drones = sum(
            intent.drone.finished_traversal for intent in accepted_intents
        )
        self.active_drones = [
            drone
            for drone in self.active_drones
            if not drone.finished_traversal
        ]
        if not movements and self.active_drones:
            raise RuntimeError("Simulation deadlock: no drone can move")
        self.turn_number += 1
        self.moved_drones_per_turn.append(len(accepted_intents))
        self.drone_completion_turns.extend(
            [self.turn_number] * completed_drones
        )
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
        self.moved_drones_per_turn.clear()
        self.drone_completion_turns.clear()
        self.turn_number = 0
        Drone.reset()
        self.graph.reset()

    def _print_performance_metrics(self) -> None:
        """Print statistics without adding them to the output file."""
        average_turns = (
            sum(self.drone_completion_turns) / self.nb_drones
            if self.nb_drones
            else 0.0
        )
        print("------------------------------")
        print("Performance metrics")
        print(f"Total turns: {self.turn_number}")
        print(f"Average turns per drone: {average_turns:.2f}")
        print("Moved drones per turn:")
        for turn, moved_drones in enumerate(
            self.moved_drones_per_turn,
            start=1,
        ):
            print(f"Turn {turn}: {moved_drones}")
        print("------------------------------")

    def _plan_turn(self) -> list[MoveIntent]:
        """Plan one turn with a global, capacity-aware throughput scheduler."""
        mandatory_arrivals: list[MoveIntent] = []
        candidate_map: dict[Drone, list[MoveIntent]] = {}
        for drone in self.active_drones:
            if drone.in_transit is not None:
                intent = drone.act()
                if intent is None:
                    raise RuntimeError(
                        f"Drone {drone.id} is in transit without an arrival"
                    )
                mandatory_arrivals.append(intent)
                continue
            candidate_map[drone] = drone.candidate_intents()

        accepted = list(mandatory_arrivals)
        waiting = list(candidate_map.keys())
        while waiting:
            progress = False
            retry: list[Drone] = []
            for drone in sorted(
                waiting,
                key=lambda current: self._drone_priority(
                    current,
                    candidate_map[current],
                ),
            ):
                chosen_intent = self._best_feasible_intent(
                    drone,
                    candidate_map[drone],
                    accepted,
                )
                if chosen_intent is None:
                    retry.append(drone)
                    continue
                accepted.append(chosen_intent)
                progress = True
            if not progress:
                waiting = retry
                break
            waiting = retry

        planned_drones = {intent.drone for intent in accepted}
        for drone in self.active_drones:
            if drone not in planned_drones:
                drone.mark_waiting()
        accepted_by_drone = {intent.drone: intent for intent in accepted}
        return [
            accepted_by_drone[drone]
            for drone in self.active_drones
            if drone in accepted_by_drone
        ]

    def _drone_priority(
        self,
        drone: Drone,
        candidates: list[MoveIntent],
    ) -> tuple[bool, int, int, float, str]:
        """Prefer drones that are blocked, inside the graph, or aging out."""
        current_zone = drone.current_zone
        in_start_zone = current_zone is self.graph.start_zone
        try:
            remaining_cost = (
                self.graph.shortest_cost_from(current_zone)
                if current_zone is not None
                else 0.0
            )
        except ValueError:
            remaining_cost = float("inf")
        return (
            in_start_zone,
            len(candidates),
            -drone.wait_turns,
            remaining_cost,
            drone.id,
        )

    def _best_feasible_intent(
        self,
        drone: Drone,
        candidates: list[MoveIntent],
        accepted: list[MoveIntent],
    ) -> MoveIntent | None:
        """Choose the best currently feasible move for one drone."""
        best_intent: MoveIntent | None = None
        best_score = float("inf")
        for intent in candidates:
            if not self._intent_is_feasible(intent, accepted):
                continue
            score = self._intent_score(drone, intent, accepted)
            if score < best_score:
                best_score = score
                best_intent = intent
        if best_intent is None:
            return None
        if best_score > self._wait_score(drone):
            return None
        return best_intent

    def _intent_is_feasible(
        self,
        intent: MoveIntent,
        accepted: list[MoveIntent],
    ) -> bool:
        """Validate one move against the current turn reservations."""
        if intent.is_arrival:
            return True
        if self._projected_connection_usage(
            intent.connection,
            accepted + [intent],
        ) > intent.connection.max_link_capacity:
            return False
        if intent.destination.is_start or intent.destination.is_end:
            return True
        projected = self._projected_occupancy(
            intent.destination,
            accepted + [intent],
        )
        return projected <= intent.destination.max_drones

    def _intent_score(
        self,
        drone: Drone,
        intent: MoveIntent,
        accepted: list[MoveIntent],
    ) -> float:
        """Score an intent using route cost plus current congestion."""
        remaining_cost = (
            intent.destination.weight
            + self.graph.shortest_cost_from(intent.destination)
        )
        route_zones = [
            intent.destination,
            *self.graph.shortest_route_from(intent.destination),
        ]
        congestion_penalty = 0.0
        for depth, zone in enumerate(route_zones[:4], start=1):
            if zone.is_start or zone.is_end:
                continue
            zone_load = self._projected_occupancy(zone, accepted)
            congestion_penalty += (
                zone_load / max(zone.max_drones, 1)
            ) / depth

        route_connections = [intent.connection]
        current_zone = intent.destination
        for next_zone in route_zones[1:3]:
            route_connections.append(
                self.graph.connection_between(current_zone, next_zone)
            )
            current_zone = next_zone
        for depth, connection in enumerate(route_connections, start=1):
            connection_load = self._projected_connection_usage(
                connection,
                accepted,
            )
            congestion_penalty += (
                connection_load / connection.max_link_capacity
            ) / depth

        backtrack_penalty = 0.0
        if drone.previous_zone is intent.destination:
            backtrack_penalty = max(0.0, 4.5 - drone.wait_turns)

        return remaining_cost + congestion_penalty + backtrack_penalty

    def _wait_score(self, drone: Drone) -> float:
        """Estimate when waiting is still better than taking a detour."""
        current_zone = drone.current_zone
        if current_zone is None or current_zone is self.graph.end_zone:
            return 0.0
        remaining_cost = self.graph.shortest_cost_from(current_zone)
        patience_bonus = min(drone.wait_turns, 4) * 0.75
        return remaining_cost + 2.0 + patience_bonus

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

    def _projected_connection_usage(
        self,
        connection: Connection,
        accepted: list[MoveIntent],
    ) -> int:
        """Calculate the connection usage after accepted movements commit."""
        current_usage = len(connection.drones_in)
        arrivals = sum(
            intent.is_arrival and intent.connection is connection
            for intent in accepted
        )
        new_traversals = sum(
            not intent.is_arrival and intent.connection is connection
            for intent in accepted
        )
        return current_usage - arrivals + new_traversals

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
