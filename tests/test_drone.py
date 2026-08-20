"""Tests for drone identity, pathfinding, and traversal."""

import tempfile
import unittest
from pathlib import Path

from src.drone import Drone
from src.fly_in import Simulation


class DroneTests(unittest.TestCase):
    """Verify the core behavior of the Drone entity."""

    def setUp(self) -> None:
        """Create a temporary map file for each test."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.map_path = Path(self.temporary_directory.name) / "map.txt"

    def tearDown(self) -> None:
        """Release temporary state and reset drone identifiers."""
        Drone.reset()
        self.temporary_directory.cleanup()

    def configure(self, map_content: str) -> Simulation:
        """Build a simulation from ``map_content``."""
        self.map_path.write_text(map_content, encoding="utf-8")
        output_path = Path(self.temporary_directory.name) / "outputs.txt"
        simulation = Simulation(str(self.map_path), str(output_path))
        simulation.configure()
        return simulation

    def test_simulation_creates_unique_drones(self) -> None:
        """Create the requested number of sequential unique identifiers."""
        simulation = self.configure(
            "nb_drones: 3\n"
            "start_hub: start 0 0\n"
            "end_hub: end 1 0\n"
            "connection: start-end\n"
        )

        self.assertEqual(
            [drone.id for drone in simulation.drones],
            ["D1", "D2", "D3"],
        )
        self.assertTrue(
            all(not drone.finished_traversal for drone in simulation.drones)
        )

    def test_act_finds_route_moves_and_finishes(self) -> None:
        """Use act as the entry point for pathfinding and movement."""
        simulation = self.configure(
            "nb_drones: 1\n"
            "start_hub: start 0 0\n"
            "hub: middle 1 0\n"
            "end_hub: end 2 0\n"
            "connection: start-middle\n"
            "connection: middle-end\n"
        )
        drone = simulation.drones[0]

        first_intent = drone.act()
        self.assertIsNotNone(first_intent)
        assert first_intent is not None
        self.assertEqual(first_intent.destination.name, "middle")

        simulation.next_turn()
        second_intent = drone.act()
        self.assertIsNotNone(second_intent)
        assert second_intent is not None
        self.assertEqual(second_intent.destination.name, "end")
        simulation.next_turn()

        self.assertTrue(drone.finished_traversal)
        self.assertIsNone(drone.act())

    def test_pathfinding_prefers_priority_zone(self) -> None:
        """Prefer a lower weighted priority route over a normal route."""
        simulation = self.configure(
            "nb_drones: 1\n"
            "start_hub: start 0 0\n"
            "hub: normal_path 1 0\n"
            "hub: priority_path 1 1 [zone=priority]\n"
            "end_hub: end 2 0\n"
            "connection: start-normal_path\n"
            "connection: normal_path-end\n"
            "connection: start-priority_path\n"
            "connection: priority_path-end\n"
        )
        drone = simulation.drones[0]

        route = drone.path_finding()

        self.assertEqual(
            [zone.name for zone in route],
            ["priority_path", "end"],
        )

    def test_pathfinding_avoids_blocked_zone(self) -> None:
        """Never include blocked zones in a calculated route."""
        simulation = self.configure(
            "nb_drones: 1\n"
            "start_hub: start 0 0\n"
            "hub: blocked_path 1 0 [zone=blocked]\n"
            "hub: open_path 1 1\n"
            "end_hub: end 2 0\n"
            "connection: start-blocked_path\n"
            "connection: blocked_path-end\n"
            "connection: start-open_path\n"
            "connection: open_path-end\n"
        )
        route = simulation.drones[0].path_finding()

        self.assertEqual([zone.name for zone in route], ["open_path", "end"])

    def test_pathfinding_reports_unreachable_destination(self) -> None:
        """Raise a clear error when no traversable route exists."""
        simulation = self.configure(
            "nb_drones: 1\n"
            "start_hub: start 0 0\n"
            "hub: blocked_path 1 0 [zone=blocked]\n"
            "end_hub: end 2 0\n"
            "connection: start-blocked_path\n"
            "connection: blocked_path-end\n"
        )

        with self.assertRaisesRegex(ValueError, "No route available for D1"):
            simulation.drones[0].act()

    def test_reconfiguration_restarts_identifiers(self) -> None:
        """Restart identifiers when rebuilding an entire simulation."""
        simulation = self.configure(
            "nb_drones: 2\n"
            "start_hub: start 0 0\n"
            "end_hub: end 1 0\n"
            "connection: start-end\n"
        )

        simulation.configure()

        self.assertEqual(
            [drone.id for drone in simulation.drones],
            ["D1", "D2"],
        )


if __name__ == "__main__":
    unittest.main()
