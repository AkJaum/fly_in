"""End-to-end validation against the maps and targets from subject 1.6."""

import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

from src.fly_in import Simulation


class BenchmarkTests(unittest.TestCase):
    """Verify valid state and performance on every supplied benchmark map."""

    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    BENCHMARK_TARGETS: ClassVar[dict[str, int]] = {
        "maps/easy/01_linear_path.txt": 6,
        "maps/easy/02_simple_fork.txt": 8,
        "maps/easy/03_basic_capacity.txt": 6,
        "maps/medium/01_dead_end_trap.txt": 12,
        "maps/medium/02_circular_loop.txt": 15,
        "maps/medium/03_priority_puzzle.txt": 12,
        "maps/hard/01_maze_nightmare.txt": 30,
        "maps/hard/02_capacity_hell.txt": 35,
        "maps/hard/03_ultimate_challenge.txt": 45,
    }

    def setUp(self) -> None:
        """Create an isolated output location for benchmark runs."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.output_path = Path(self.temporary_directory.name) / "outputs.txt"

    def tearDown(self) -> None:
        """Release the isolated output location."""
        self.temporary_directory.cleanup()

    def test_subject_1_6_benchmarks_and_capacity_invariants(self) -> None:
        """Meet every mandatory target without exceeding any capacity."""
        for relative_path, target in self.BENCHMARK_TARGETS.items():
            with self.subTest(map=relative_path, target=target):
                simulation = self._run_map(relative_path)
                self.assertLessEqual(simulation.turn_number, target)

    def test_challenger_beats_reference_record(self) -> None:
        """Keep the optional challenger result below the 45-turn record."""
        simulation = self._run_map(
            "maps/challenger/01_the_impossible_dream.txt"
        )
        self.assertLess(simulation.turn_number, 45)

    def _run_map(self, relative_path: str) -> Simulation:
        """Run one map and check domain invariants after every turn."""
        map_path = self.PROJECT_ROOT / relative_path
        simulation = Simulation(str(map_path), str(self.output_path))
        simulation.configure()

        while simulation.active_drones:
            simulation.next_turn()
            self._assert_capacity_invariants(simulation)

        self.assertTrue(
            all(drone.finished_traversal for drone in simulation.drones)
        )
        self.assertEqual(len(simulation.turn_outputs), simulation.turn_number)
        return simulation

    def _assert_capacity_invariants(self, simulation: Simulation) -> None:
        """Reject zone, connection, or transit state inconsistencies."""
        for zone in simulation.graph.zones.values():
            if not zone.is_start and not zone.is_end:
                self.assertLessEqual(len(zone.drones_in), zone.max_drones)

        for connection in simulation.graph.connections:
            self.assertLessEqual(
                len(connection.drones_in),
                connection.max_link_capacity,
            )

        for drone in simulation.active_drones:
            if drone.in_transit is None:
                self.assertIsNotNone(drone.current_zone)
                self.assertIsNone(drone.transit_destination)
            else:
                self.assertIsNone(drone.current_zone)
                self.assertIsNotNone(drone.transit_destination)


if __name__ == "__main__":
    unittest.main()
