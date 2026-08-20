"""Tests for the object-oriented simulation lifecycle."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from src.fly_in import Simulation
from src.ZoneHub import Connection, Zone


class SimulationTests(unittest.TestCase):
    """Verify configuration and startup behavior."""

    VALID_MAP = """\
nb_drones: 2
start_hub: start 0 0
hub: middle 1 0 [zone=priority max_drones=2]
end_hub: end 2 0
connection: start-middle [max_link_capacity=2]
connection: middle-end
"""

    def setUp(self) -> None:
        """Create an isolated temporary map path."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.map_path = Path(self.temporary_directory.name) / "map.txt"
        self.output_path = Path(self.temporary_directory.name) / "outputs.txt"

    def simulation(self) -> Simulation:
        """Create a simulation using isolated input and output files."""
        return Simulation(str(self.map_path), str(self.output_path))

    def tearDown(self) -> None:
        """Release temporary files and shared domain registries."""
        Zone.reset()
        Connection.reset()
        self.temporary_directory.cleanup()

    def test_configure_builds_complete_simulation_state(self) -> None:
        """Build parser, graph, endpoints, and drone count in one call."""
        self.map_path.write_text(self.VALID_MAP, encoding="utf-8")
        simulation = self.simulation()

        simulation.configure()

        self.assertTrue(simulation.is_configured)
        self.assertEqual(simulation.nb_drones, 2)
        self.assertEqual(len(simulation.drones), 2)
        self.assertEqual(len(simulation.active_drones), 2)
        self.assertEqual(len(simulation.graph.zones), 3)
        self.assertEqual(len(simulation.graph.connections), 2)
        start_zone = simulation.graph.start_zone
        end_zone = simulation.graph.end_zone
        self.assertIsNotNone(start_zone)
        self.assertIsNotNone(end_zone)
        assert start_zone is not None
        assert end_zone is not None
        self.assertEqual(start_zone.name, "start")
        self.assertEqual(end_zone.name, "end")
        self.assertEqual(
            len(simulation.graph.zones["middle"].connections),
            2,
        )

    def test_configure_can_replace_previous_state(self) -> None:
        """Ensure repeated configuration never accumulates domain objects."""
        self.map_path.write_text(self.VALID_MAP, encoding="utf-8")
        simulation = self.simulation()
        simulation.configure()

        replacement_map = self.VALID_MAP.replace(
            "nb_drones: 2",
            "nb_drones: 5",
        )
        self.map_path.write_text(replacement_map, encoding="utf-8")
        simulation.configure()

        self.assertEqual(simulation.nb_drones, 5)
        self.assertEqual(len(Zone._all_zones), 3)
        self.assertEqual(len(Connection._all_connections), 2)

    def test_failed_configuration_leaves_clean_state(self) -> None:
        """Do not expose stale state after an invalid map is attempted."""
        self.map_path.write_text("nb_drones: 0\n", encoding="utf-8")
        simulation = self.simulation()

        with self.assertRaises(ValueError):
            simulation.configure()

        self.assertFalse(simulation.is_configured)
        self.assertEqual(simulation.nb_drones, 0)
        self.assertEqual(simulation.drones, [])
        self.assertEqual(simulation.active_drones, [])
        self.assertEqual(simulation.graph.zones, {})

    def test_next_turn_moves_every_active_drone(self) -> None:
        """Act with all active drones and format one subject output line."""
        self.map_path.write_text(self.VALID_MAP, encoding="utf-8")
        simulation = self.simulation()
        simulation.configure()

        first_turn = simulation.next_turn()
        second_turn = simulation.next_turn()
        third_turn = simulation.next_turn()

        self.assertEqual(first_turn, "D1-middle D2-middle")
        self.assertEqual(second_turn, "D1-end")
        self.assertEqual(third_turn, "D2-end")
        self.assertEqual(simulation.turn_number, 3)
        self.assertEqual(simulation.active_drones, [])
        self.assertEqual(simulation.next_turn(), "")
        self.assertEqual(simulation.turn_number, 3)
        self.assertTrue(
            all(drone.finished_traversal for drone in simulation.drones)
        )

    def test_start_prints_terminal_only_metrics(self) -> None:
        """Print movements and metrics without persisting statistics."""
        self.map_path.write_text(self.VALID_MAP, encoding="utf-8")
        simulation = self.simulation()

        with contextlib.redirect_stdout(io.StringIO()) as output:
            simulation.start()

        self.assertTrue(simulation.is_configured)
        self.assertEqual(
            output.getvalue().splitlines(),
            [
                "D1-middle D2-middle",
                "D1-end",
                "D2-end",
                "------------------------------",
                "Performance metrics",
                "Total turns: 3",
                "Average turns per drone: 2.50",
                "Moved drones per turn:",
                "Turn 1: 2",
                "Turn 2: 1",
                "Turn 3: 1",
                "------------------------------",
            ],
        )
        self.assertEqual(
            self.output_path.read_text(encoding="utf-8").splitlines(),
            ["D1-middle D2-middle", "D1-end", "D2-end"],
        )

    def test_reconfiguration_clears_turn_history(self) -> None:
        """Reset time, output, and active drones during configuration."""
        self.map_path.write_text(self.VALID_MAP, encoding="utf-8")
        simulation = self.simulation()
        simulation.configure()
        simulation.next_turn()

        simulation.configure()

        self.assertEqual(simulation.turn_number, 0)
        self.assertEqual(simulation.turn_outputs, [])
        self.assertEqual(simulation.moved_drones_per_turn, [])
        self.assertEqual(simulation.drone_completion_turns, [])
        self.assertEqual(len(simulation.active_drones), 2)
        self.assertEqual(self.output_path.read_text(encoding="utf-8"), "")

    def test_departure_frees_zone_capacity_in_same_turn(self) -> None:
        """Allow an arrival when the current occupant leaves simultaneously."""
        self.map_path.write_text(
            "nb_drones: 2\n"
            "start_hub: start 0 0\n"
            "hub: middle 1 0 [max_drones=1]\n"
            "end_hub: end 2 0\n"
            "connection: start-middle\n"
            "connection: middle-end\n",
            encoding="utf-8",
        )
        simulation = self.simulation()
        simulation.configure()

        self.assertEqual(simulation.next_turn(), "D1-middle")
        self.assertEqual(simulation.next_turn(), "D1-end D2-middle")
        self.assertEqual(len(simulation.graph.zones["middle"].drones_in), 1)

    def test_start_and_end_ignore_max_drones_metadata(self) -> None:
        """Keep start and end hubs effectively unlimited despite metadata."""
        self.map_path.write_text(
            "nb_drones: 3\n"
            "start_hub: start 0 0 [max_drones=1]\n"
            "hub: middle 1 0 [max_drones=3]\n"
            "end_hub: end 2 0 [max_drones=1]\n"
            "connection: start-middle [max_link_capacity=3]\n"
            "connection: middle-end [max_link_capacity=3]\n",
            encoding="utf-8",
        )
        simulation = self.simulation()
        simulation.configure()

        start_zone = simulation.graph.start_zone
        self.assertIsNotNone(start_zone)
        assert start_zone is not None
        self.assertEqual(len(start_zone.drones_in), 3)
        self.assertEqual(
            simulation.next_turn(),
            "D1-middle D2-middle D3-middle",
        )
        self.assertEqual(
            simulation.next_turn(),
            "D1-end D2-end D3-end",
        )

    def test_restricted_zone_uses_connection_then_arrives(self) -> None:
        """Enter a connection first and reach its restricted zone next turn."""
        self.map_path.write_text(
            "nb_drones: 1\n"
            "start_hub: start 0 0\n"
            "hub: tunnel 1 0 [zone=restricted]\n"
            "end_hub: end 2 0\n"
            "connection: start-tunnel\n"
            "connection: tunnel-end\n",
            encoding="utf-8",
        )
        simulation = self.simulation()
        simulation.configure()
        drone = simulation.drones[0]

        self.assertEqual(simulation.next_turn(), "D1-start-tunnel")
        self.assertIsNone(drone.current_zone)
        self.assertEqual(len(simulation.graph.connections[0].drones_in), 1)
        self.assertEqual(simulation.next_turn(), "D1-tunnel")
        current_zone = drone.current_zone
        self.assertIsNotNone(current_zone)
        assert current_zone is not None
        self.assertEqual(current_zone.name, "tunnel")
        self.assertEqual(len(simulation.graph.connections[0].drones_in), 0)
        self.assertFalse(drone.finished_traversal)

    def test_global_scheduler_splits_equal_paths(self) -> None:
        """Spread drones across equal routes instead of queueing one branch."""
        self.map_path.write_text(
            "nb_drones: 2\n"
            "start_hub: start 0 0\n"
            "hub: north 1 1\n"
            "hub: south 1 -1\n"
            "hub: north_mid 2 1\n"
            "hub: south_mid 2 -1\n"
            "end_hub: end 3 0\n"
            "connection: start-north\n"
            "connection: start-south\n"
            "connection: north-north_mid\n"
            "connection: south-south_mid\n"
            "connection: north_mid-end\n"
            "connection: south_mid-end\n",
            encoding="utf-8",
        )
        simulation = self.simulation()
        simulation.configure()

        self.assertEqual(
            simulation.next_turn(),
            "D1-north D2-south",
        )

    def test_global_scheduler_uses_longer_route_for_better_throughput(
        self,
    ) -> None:
        """Replan globally when waiting on the best local path hurts flow."""
        self.map_path.write_text(
            "nb_drones: 2\n"
            "start_hub: start 0 0\n"
            "hub: short 1 0\n"
            "hub: long_1 1 1\n"
            "hub: long_2 2 1\n"
            "hub: merge 2 0 [max_drones=2]\n"
            "end_hub: end 3 0\n"
            "connection: start-short\n"
            "connection: short-merge\n"
            "connection: start-long_1\n"
            "connection: long_1-long_2\n"
            "connection: long_2-merge\n"
            "connection: merge-end [max_link_capacity=2]\n",
            encoding="utf-8",
        )
        simulation = self.simulation()
        simulation.configure()

        self.assertEqual(
            simulation.next_turn(),
            "D1-short D2-long_1",
        )
        self.assertEqual(simulation.next_turn(), "D1-merge D2-long_2")
        self.assertEqual(simulation.next_turn(), "D1-end D2-merge")
        self.assertEqual(simulation.next_turn(), "D2-end")
        self.assertEqual(simulation.turn_number, 4)

    def test_execute_returns_failure_for_invalid_input(self) -> None:
        """Translate configuration failures into a nonzero status code."""
        self.map_path.write_text("nb_drones: nope\n", encoding="utf-8")
        simulation = self.simulation()

        with contextlib.redirect_stderr(io.StringIO()) as error_output:
            status = simulation.execute()

        self.assertEqual(status, 1)
        self.assertIn("Line 1", error_output.getvalue())


if __name__ == "__main__":
    unittest.main()
