"""Tests for Fly-in map parsing and input validation."""

import tempfile
import unittest
from pathlib import Path

from src.parser import MapParser, ParsedMapData


class MapParserTests(unittest.TestCase):
    """Verify valid maps and every parser-owned error category."""

    VALID_MAP = """\
# Leading comments are allowed.
nb_drones: 3
start_hub: start 0 0 [max_drones=3 color=green]
hub: fast 1 -2 [color=blue zone=priority max_drones=2]
hub: tunnel 2 0 [zone=restricted]
end_hub: goal 3 0
connection: start-fast [max_link_capacity=2]
connection: fast-tunnel
connection: tunnel-goal
"""

    def parse(self, content: str) -> ParsedMapData:
        """Parse ``content`` through a temporary map file."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.txt"
            path.write_text(content, encoding="utf-8")
            return MapParser(str(path)).parse_file()

    def assert_parse_error(self, content: str, message: str) -> None:
        """Assert that parsing fails with a line-aware expected message."""
        with self.assertRaisesRegex(ValueError, rf"Line \d+: .*{message}"):
            self.parse(content)

    def test_valid_map_and_defaults(self) -> None:
        """Parse valid declarations, arbitrary metadata order, and defaults."""
        parsed = self.parse(self.VALID_MAP)
        self.assertEqual(parsed["nb_drones"], 3)
        hubs = parsed["hubs"]
        self.assertIsInstance(hubs, list)
        self.assertEqual(hubs[0]["kind"], "normal")
        self.assertEqual(hubs[1]["kind"], "priority")
        self.assertEqual(hubs[1]["y"], -2)
        self.assertEqual(hubs[2]["kind"], "restricted")
        self.assertEqual(hubs[3]["max_drones"], 1)
        self.assertEqual(
            parsed["connections"][0]["max_link_capacity"], 2
        )

    def test_disconnected_map_is_parser_valid(self) -> None:
        """Leave graph reachability checks to the graph or simulation layer."""
        parsed = self.parse(
            "nb_drones: 1\n"
            "start_hub: start 0 0\n"
            "end_hub: end 1 0\n"
        )
        self.assertEqual(parsed["connections"], [])

    def test_parser_instance_can_be_reused(self) -> None:
        """Do not accumulate declarations across repeated parsing calls."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.txt"
            path.write_text(self.VALID_MAP, encoding="utf-8")
            parser = MapParser(str(path))
            self.assertEqual(parser.parse_file(), parser.parse_file())

    def test_empty_file(self) -> None:
        """Reject files without declarations."""
        self.assert_parse_error("# only a comment\n", "map file is empty")

    def test_first_declaration_must_be_drone_count(self) -> None:
        """Require nb_drones before all other meaningful declarations."""
        self.assert_parse_error(
            "hub: first 0 0\nnb_drones: 1\n",
            "first declaration must define nb_drones",
        )

    def test_drone_count_errors(self) -> None:
        """Reject absent, repeated, malformed, and nonpositive counts."""
        self.assert_parse_error("nb_drones: 0\n", "greater than zero")
        self.assert_parse_error("nb_drones: -1\n", "positive integer")
        self.assert_parse_error("nb_drones: one\n", "positive integer")
        self.assert_parse_error(
            "nb_drones: 1 [color=red]\n",
            "does not accept metadata",
        )
        self.assert_parse_error(
            "nb_drones: 1\nnb_drones: 2\n",
            "may only be declared once",
        )

    def test_required_unique_start_and_end(self) -> None:
        """Require exactly one start hub and one end hub."""
        self.assert_parse_error(
            "nb_drones: 1\nend_hub: end 0 0\n",
            "exactly one start_hub",
        )
        self.assert_parse_error(
            "nb_drones: 1\nstart_hub: start 0 0\n",
            "exactly one end_hub",
        )
        self.assert_parse_error(
            "nb_drones: 1\n"
            "start_hub: one 0 0\n"
            "start_hub: two 1 0\n"
            "end_hub: end 2 0\n",
            "exactly one start_hub",
        )
        self.assert_parse_error(
            "nb_drones: 1\n"
            "start_hub: start 0 0\n"
            "end_hub: one 1 0\n"
            "end_hub: two 2 0\n",
            "exactly one end_hub",
        )

    def test_zone_structure_and_values(self) -> None:
        """Reject invalid zone fields, names, coordinates, and types."""
        prefix = "nb_drones: 1\n"
        self.assert_parse_error(
            prefix + "start_hub: start 0\n", "requires exactly"
        )
        self.assert_parse_error(
            prefix + "start_hub: bad-name 0 0\n", "invalid zone name"
        )
        self.assert_parse_error(
            prefix + "start_hub: start x 0\n", "coordinate must be an integer"
        )
        self.assert_parse_error(
            prefix + "start_hub: start 0 0 [zone=banana]\n",
            "invalid zone type",
        )
        self.assert_parse_error(
            prefix
            + "start_hub: same 0 0\n"
            + "end_hub: same 1 0\n",
            "duplicate zone",
        )

    def test_metadata_syntax_and_schema(self) -> None:
        """Reject incomplete, unknown, duplicate, and misplaced metadata."""
        prefix = "nb_drones: 1\n"
        self.assert_parse_error(
            prefix + "start_hub: start 0 0 [zone=normal\n",
            "malformed metadata",
        )
        self.assert_parse_error(
            prefix + "start_hub: start 0 0 [zone]\n",
            "invalid metadata token",
        )
        self.assert_parse_error(
            prefix + "start_hub: start 0 0 [unknown=value]\n",
            "not valid for a zone",
        )
        self.assert_parse_error(
            prefix + "start_hub: start 0 0 [zone=normal zone=priority]\n",
            "duplicate metadata key",
        )

    def test_capacity_values(self) -> None:
        """Require positive integer zone and connection capacities."""
        self.assert_parse_error(
            "nb_drones: 1\nstart_hub: start 0 0 [max_drones=0]\n",
            "max_drones must be greater than zero",
        )
        self.assert_parse_error(
            "nb_drones: 1\nstart_hub: start 0 0 [max_drones=-1]\n",
            "max_drones must be a positive integer",
        )
        self.assert_parse_error(
            "nb_drones: 1\n"
            "start_hub: start 0 0\n"
            "end_hub: end 1 0\n"
            "connection: start-end [max_link_capacity=many]\n",
            "max_link_capacity must be a positive integer",
        )

    def test_connection_structure_and_references(self) -> None:
        """Validate connection shape, order, endpoints, and metadata."""
        prefix = (
            "nb_drones: 1\n"
            "start_hub: start 0 0\n"
            "end_hub: end 1 0\n"
        )
        self.assert_parse_error(
            prefix + "connection: start\n", "requires exactly"
        )
        self.assert_parse_error(
            prefix + "connection: start- end\n", "cannot contain spaces"
        )
        self.assert_parse_error(
            prefix + "connection: start-start\n", "cannot connect to itself"
        )
        self.assert_parse_error(
            prefix + "connection: start-missing\n",
            "before its declaration",
        )
        self.assert_parse_error(
            "nb_drones: 1\n"
            "connection: start-end\n"
            "start_hub: start 0 0\n"
            "end_hub: end 1 0\n",
            "before its declaration",
        )
        self.assert_parse_error(
            prefix + "connection: start-end [zone=normal]\n",
            "not valid for a connection",
        )

    def test_duplicate_undirected_connections(self) -> None:
        """Treat a-b and b-a as the same connection."""
        prefix = (
            "nb_drones: 1\n"
            "start_hub: start 0 0\n"
            "end_hub: end 1 0\n"
            "connection: start-end\n"
        )
        self.assert_parse_error(
            prefix + "connection: start-end\n", "duplicate connection"
        )
        self.assert_parse_error(
            prefix + "connection: end-start\n", "duplicate connection"
        )

    def test_unknown_and_malformed_declarations(self) -> None:
        """Reject unknown keys and declarations with malformed grammar."""
        self.assert_parse_error(
            "nb_drones: 1\nteleporter: a-b\n", "unknown declaration"
        )
        self.assert_parse_error(
            "nb_drones: 1\nhub without colon\n", "invalid declaration"
        )


if __name__ == "__main__":
    unittest.main()
