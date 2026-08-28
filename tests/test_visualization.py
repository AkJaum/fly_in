"""Tests for the browser-facing simulation adapter and SVG renderer."""

import re
import tempfile
import unittest
from pathlib import Path

from src.drone import Drone
from src.visualization import (
    BrowserSimulation,
    DroneLocation,
    SvgMapRenderer,
)
from src.ZoneHub import Connection, Zone


class VisualizationTests(unittest.TestCase):
    """Verify the browser visual layer without starting a web server."""

    SIMPLE_MAP = """\
nb_drones: 2
start_hub: start 0 0 [color=green]
hub: middle 1 0 [color=blue]
end_hub: goal 2 0 [color=red]
connection: start-middle
connection: middle-goal
"""

    def setUp(self) -> None:
        """Create a minimal isolated Fly-in project tree."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temporary_directory.name)
        self.output_path = self.project_root / "outputs.txt"
        (self.project_root / "map.txt").write_text(
            self.SIMPLE_MAP,
            encoding="utf-8",
        )
        extra_maps = self.project_root / "maps" / "easy"
        extra_maps.mkdir(parents=True)
        (extra_maps / "other.txt").write_text(
            self.SIMPLE_MAP,
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        """Release files and shared domain registries."""
        Drone.reset()
        Zone.reset()
        Connection.reset()
        self.temporary_directory.cleanup()

    def test_controller_discovers_steps_and_resets_maps(self) -> None:
        """Drive the existing simulation through the browser adapter."""
        controller = BrowserSimulation(self.project_root, self.output_path)

        self.assertEqual(
            list(controller.available_maps),
            ["map.txt", "maps/easy/other.txt"],
        )
        controller.configure()
        initial = controller.snapshot()
        self.assertEqual(initial.turn, 0)
        self.assertEqual(initial.active_drones, 2)
        self.assertEqual(initial.delivered_drones, 0)

        self.assertEqual(controller.step(), "D1-middle")
        self.assertEqual(controller.snapshot().turn, 1)
        self.assertEqual(controller.snapshot().moved_drones, 1)
        self.assertEqual(controller.snapshot().waiting_drones, 1)
        self.assertEqual(controller.last_transitions[0].drone_id, "D1")
        self.assertEqual(controller.last_transitions[0].origin.name, "start")
        self.assertEqual(
            controller.last_transitions[0].destination.name,
            "middle",
        )
        controller.reset()
        self.assertEqual(controller.snapshot().turn, 0)
        self.assertEqual(controller.last_transitions, ())

    def test_svg_shows_zones_connections_and_occupancy(self) -> None:
        """Render meaningful graph and drone state from domain objects."""
        controller = BrowserSimulation(self.project_root, self.output_path)
        controller.configure()
        renderer = SvgMapRenderer()

        initial_svg = renderer.render(controller.simulation_or_raise())
        self.assertIn("Fly-in live drone network", initial_svg)
        self.assertIn("start: normal; 2/∞ drones", initial_svg)
        self.assertIn("start-middle: 0/1 in transit", initial_svg)
        self.assertIn("D1 at start", initial_svg)
        self.assertIn('fill="green"', initial_svg)
        self.assertIn('class="drone-silhouette"', initial_svg)
        self.assertIn('class="drone-status-light"', initial_svg)
        self.assertIn('class="drone-rotor"', initial_svg)
        self.assertIn('data-base-width="1000.0"', initial_svg)
        self.assertIn('data-base-height="600.0"', initial_svg)
        self.assertIn('class="drone-cluster"', initial_svg)
        self.assertIn('data-orbit-x=', initial_svg)
        self.assertIn(
            'class="occupancy-summary screen-fixed-marker"',
            initial_svg,
        )

        controller.step()
        moved_svg = renderer.render(
            controller.simulation_or_raise(),
            controller.last_transitions,
        )
        self.assertIn("start: normal; 1/∞ drones", moved_svg)
        self.assertIn("middle: normal; 1/1 drones", moved_svg)
        self.assertIn('class="movement-trace"', moved_svg)
        self.assertIn("animateMotion", moved_svg)
        self.assertIn('class="map-world"', moved_svg)
        self.assertIn('class="zone-node"', moved_svg)
        self.assertIn('class="connection-node"', moved_svg)
        self.assertIn('id="canvas-grid"', moved_svg)
        self.assertIn('class="departure-beacon"', moved_svg)
        self.assertIn('class="movement-path"', moved_svg)
        self.assertIn('class="arrival-beacon"', moved_svg)
        self.assertIn('begin="0.2s" dur="0.82s"', moved_svg)
        self.assertIn("D1: moved", moved_svg)
        self.assertIn('class="drone-marker drone-moved"', moved_svg)
        self.assertIn('class="drone-marker drone-waiting"', moved_svg)

    def test_simultaneous_movements_use_separate_visual_lanes(self) -> None:
        """Keep drones moving on the same connection distinguishable."""
        parallel_map = self.SIMPLE_MAP.replace(
            "hub: middle 1 0 [color=blue]",
            "hub: middle 1 0 [max_drones=2 color=blue]",
        ).replace(
            "connection: start-middle",
            "connection: start-middle [max_link_capacity=2]",
        )
        (self.project_root / "map.txt").write_text(
            parallel_map,
            encoding="utf-8",
        )
        controller = BrowserSimulation(self.project_root, self.output_path)
        controller.configure()

        self.assertEqual(controller.step(), "D1-middle D2-middle")
        svg = SvgMapRenderer().render(
            controller.simulation_or_raise(),
            controller.last_transitions,
        )
        movement_paths = re.findall(
            r'<path d="(M [^"]+)" fill="none" stroke="[^"]+" '
            r'stroke-width="4" stroke-dasharray="10 8" '
            r'marker-end="[^"]+" class="movement-path"/>',
            svg,
        )

        self.assertEqual(len(movement_paths), 2)
        self.assertNotEqual(movement_paths[0], movement_paths[1])

    def test_complex_map_enables_semantic_zoom_markup(self) -> None:
        """Flag dense graphs so labels can appear progressively on zoom."""
        hubs = "\n".join(
            f"hub: node{index} {index} {index % 3} [color=blue]"
            for index in range(1, 13)
        )
        connections = ["connection: start-node1"]
        connections.extend(
            f"connection: node{index}-node{index + 1}"
            for index in range(1, 12)
        )
        connections.append("connection: node12-goal")
        connection_lines = "\n".join(connections)
        complex_map = (
            "nb_drones: 1\n"
            "start_hub: start 0 0 [color=green]\n"
            f"{hubs}\n"
            "end_hub: goal 13 1 [color=red]\n"
            f"{connection_lines}\n"
        )
        (self.project_root / "map.txt").write_text(
            complex_map,
            encoding="utf-8",
        )
        controller = BrowserSimulation(self.project_root, self.output_path)
        controller.configure()

        svg = SvgMapRenderer().render(controller.simulation_or_raise())

        self.assertIn('class="flyin-map map-complex"', svg)
        self.assertIn('class="map-world"', svg)
        self.assertIn('class="connection-badge"', svg)
        self.assertIn('class="zone-detail"', svg)

        width_match = re.search(r'data-base-width="([0-9.]+)"', svg)
        height_match = re.search(r'data-base-height="([0-9.]+)"', svg)
        if width_match is None or height_match is None:
            self.fail("adaptive canvas metadata is missing")
        self.assertGreater(float(width_match.group(1)), 1200)
        self.assertGreater(float(height_match.group(1)), 600)

    def test_adaptive_layout_preserves_minimum_coordinate_spacing(
        self,
    ) -> None:
        """Give dense maps room without changing relative graph geometry."""
        controller = BrowserSimulation(self.project_root, self.output_path)
        controller.configure()
        renderer = SvgMapRenderer()
        zones = list(controller.simulation_or_raise().graph.zones.values())

        positions, canvas = renderer._adaptive_layout(zones)
        ordered_positions = [positions[zone] for zone in zones]

        self.assertEqual(canvas, (0.0, 0.0, 1000.0, 600.0))
        self.assertEqual(
            ordered_positions[1][0] - ordered_positions[0][0],
            renderer.HORIZONTAL_GAP,
        )
        self.assertEqual(
            ordered_positions[2][0] - ordered_positions[1][0],
            renderer.HORIZONTAL_GAP,
        )
        self.assertEqual(
            {position[1] for position in ordered_positions},
            {renderer.MIN_HEIGHT / 2},
        )

    def test_zone_types_have_distinct_silhouettes(self) -> None:
        """Differentiate zone rules by shape without relying on a legend."""
        shaped_map = """\
nb_drones: 1
start_hub: start 0 0 [color=green]
hub: fast 1 1 [zone=priority color=lime]
hub: tunnel 2 0 [zone=restricted color=orange]
hub: closed 1 -1 [zone=blocked color=gray]
end_hub: goal 3 0 [color=blue]
connection: start-fast
connection: fast-tunnel
connection: tunnel-goal
connection: start-closed
"""
        (self.project_root / "map.txt").write_text(
            shaped_map,
            encoding="utf-8",
        )
        controller = BrowserSimulation(self.project_root, self.output_path)
        controller.configure()

        svg = SvgMapRenderer().render(controller.simulation_or_raise())

        self.assertIn("<polygon", svg)
        self.assertIn('transform="rotate(45', svg)
        self.assertIn('stroke-dasharray="7 5"', svg)
        self.assertIn(">P</text>", svg)
        self.assertIn(">R</text>", svg)
        self.assertIn(">X</text>", svg)

    def test_restricted_turns_are_visually_distinct(self) -> None:
        """Expose both the connection transit and restricted arrival turns."""
        restricted_map = """\
nb_drones: 1
start_hub: start 0 0 [color=green]
hub: tunnel 1 0 [zone=restricted color=orange]
end_hub: goal 2 0 [color=rainbow]
connection: start-tunnel
connection: tunnel-goal
"""
        (self.project_root / "map.txt").write_text(
            restricted_map,
            encoding="utf-8",
        )
        controller = BrowserSimulation(self.project_root, self.output_path)
        controller.configure()

        self.assertEqual(controller.step(), "D1-start-tunnel")
        first_turn = controller.last_transitions[0]
        self.assertEqual(first_turn.destination.kind, "connection")
        self.assertEqual(
            first_turn.status,
            "restricted transit: turn 1 of 2",
        )
        self.assertEqual(controller.snapshot().in_transit_drones, 1)
        transit_svg = SvgMapRenderer().render(
            controller.simulation_or_raise(),
            controller.last_transitions,
        )
        self.assertIn("D1 at start-tunnel", transit_svg)
        self.assertIn("restricted transit: turn 1 of 2", transit_svg)

        self.assertEqual(controller.step(), "D1-tunnel")
        second_turn = controller.last_transitions[0]
        self.assertEqual(second_turn.origin.kind, "connection")
        self.assertEqual(
            second_turn.status,
            "restricted arrival: turn 2 of 2",
        )
        self.assertEqual(controller.snapshot().in_transit_drones, 0)
        self.assertIn(
            'fill="url(#rainbow-zone)"',
            SvgMapRenderer().render(controller.simulation_or_raise()),
        )

    def test_manifest_reports_exact_drone_locations(self) -> None:
        """List every drone even when the SVG groups a large occupancy."""
        controller = BrowserSimulation(self.project_root, self.output_path)
        controller.configure()

        locations = controller.drone_locations()

        self.assertEqual(
            locations,
            (
                ("D1", DroneLocation("zone", "start"), "active"),
                ("D2", DroneLocation("zone", "start"), "active"),
            ),
        )
        self.assertEqual(locations[0][1].label, "zone start")

    def test_svg_escapes_map_controlled_text(self) -> None:
        """Prevent zone names from injecting markup into the visualizer."""
        unsafe_map = self.SIMPLE_MAP.replace("middle", "<middle>")
        (self.project_root / "map.txt").write_text(
            unsafe_map,
            encoding="utf-8",
        )
        controller = BrowserSimulation(self.project_root, self.output_path)
        controller.configure()

        svg = SvgMapRenderer().render(controller.simulation_or_raise())

        self.assertIn("&lt;middle&gt;", svg)
        self.assertNotIn("<middle>", svg)

    def test_controller_rejects_unknown_map(self) -> None:
        """Never allow arbitrary paths through the map selector."""
        controller = BrowserSimulation(self.project_root, self.output_path)

        with self.assertRaisesRegex(ValueError, "Unknown project map"):
            controller.configure("../../outside.txt")

    def test_controller_accepts_explicit_external_map(self) -> None:
        """Allow evaluation maps supplied outside the repository tree."""
        with tempfile.TemporaryDirectory() as external_directory:
            external_map = Path(external_directory) / "evaluation.txt"
            external_map.write_text(self.SIMPLE_MAP, encoding="utf-8")

            controller = BrowserSimulation(
                self.project_root,
                self.output_path,
                external_map,
            )
            controller.configure()

            self.assertTrue(
                controller.selected_map.startswith("external: ")
            )
            self.assertEqual(controller.snapshot().total_drones, 2)


if __name__ == "__main__":
    unittest.main()
