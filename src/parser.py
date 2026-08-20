"""Parse and validate Fly-in map files."""

import re
from typing import NoReturn, TypedDict


class HubData(TypedDict):
    """Intermediate representation of a parsed hub."""

    name: str
    kind: str
    x: int
    y: int
    is_start: bool
    is_end: bool
    color: str | None
    max_drones: int


ConnectionData = TypedDict(
    "ConnectionData",
    {"from": str, "to": str, "max_link_capacity": int},
)


class ParsedMapData(TypedDict):
    """Complete intermediate representation of a map."""

    nb_drones: int
    hubs: list[HubData]
    connections: list[ConnectionData]


class MapParser:
    """Parse a map file and validate its input-level constraints."""

    _DECLARATION_PATTERN = re.compile(
        r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*):\s*(?P<body>.+)$"
    )
    _METADATA_PATTERN = re.compile(
        r"^(?P<value>.*?)\s+\[(?P<metadata>[^\[\]]+)\]$"
    )
    _METADATA_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    _POSITIVE_INTEGER_PATTERN = re.compile(r"^[0-9]+$")
    _ZONE_TYPES = frozenset({"normal", "blocked", "restricted", "priority"})
    _ZONE_METADATA = frozenset({"zone", "color", "max_drones"})
    _CONNECTION_METADATA = frozenset({"max_link_capacity"})

    def __init__(self, file_path: str) -> None:
        """Initialize a parser for ``file_path``."""
        self.file_path = file_path
        self._lines: list[tuple[int, str]] = []
        self._nb_drones: int | None = None
        self._hubs: list[HubData] = []
        self._connections: list[ConnectionData] = []
        self._zone_lines: dict[str, int] = {}
        self._connection_lines: dict[frozenset[str], int] = {}
        self._start_lines: list[int] = []
        self._end_lines: list[int] = []

    def parse_file(self) -> ParsedMapData:
        """Parse the configured file and return validated intermediate data."""
        self._reset()
        self._read_and_clean_data()
        self._parse_lines()
        self._validate_required_declarations()
        if self._nb_drones is None:
            raise RuntimeError("Parser validation finished without nb_drones")
        return {
            "nb_drones": self._nb_drones,
            "hubs": self._hubs,
            "connections": self._connections,
        }

    def _reset(self) -> None:
        """Clear state so a parser instance can safely run more than once."""
        self._lines.clear()
        self._nb_drones = None
        self._hubs.clear()
        self._connections.clear()
        self._zone_lines.clear()
        self._connection_lines.clear()
        self._start_lines.clear()
        self._end_lines.clear()

    def _read_and_clean_data(self) -> None:
        """Read meaningful lines and preserve their physical line numbers."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as map_file:
                for line_number, raw_line in enumerate(map_file, start=1):
                    line = raw_line.partition("#")[0].strip()
                    if line:
                        self._lines.append((line_number, line))
        except FileNotFoundError as error:
            raise ValueError(f"File not found: {self.file_path}") from error
        except (OSError, UnicodeError) as error:
            raise ValueError(
                f"Could not read map file '{self.file_path}': {error}"
            ) from error

        if not self._lines:
            self._error(1, "map file is empty")

    def _parse_lines(self) -> None:
        """Parse every meaningful declaration in source order."""
        for declaration_index, (line_number, line) in enumerate(self._lines):
            match = self._DECLARATION_PATTERN.fullmatch(line)
            if match is None:
                self._error(
                    line_number,
                    "invalid declaration; expected '<key>: <value>'",
                )

            key = match.group("key")
            value, metadata = self._split_metadata(
                match.group("body"), line_number
            )

            if declaration_index == 0 and key != "nb_drones":
                self._error(
                    line_number,
                    "the first declaration must define nb_drones",
                )

            if key == "nb_drones":
                self._parse_drone_count(value, metadata, line_number)
            elif key in {"start_hub", "hub", "end_hub"}:
                self._parse_hub(key, value, metadata, line_number)
            elif key == "connection":
                self._parse_connection(value, metadata, line_number)
            else:
                self._error(line_number, f"unknown declaration '{key}'")

    def _split_metadata(
        self, body: str, line_number: int
    ) -> tuple[str, str | None]:
        """Separate a declaration value from its optional metadata block."""
        match = self._METADATA_PATTERN.fullmatch(body)
        if match is not None:
            value = match.group("value").strip()
            if not value:
                self._error(line_number, "declaration value cannot be empty")
            return value, match.group("metadata").strip()

        if "[" in body or "]" in body:
            self._error(line_number, "malformed metadata block")
        return body.strip(), None

    def _parse_drone_count(
        self, value: str, metadata: str | None, line_number: int
    ) -> None:
        """Parse the single positive drone-count declaration."""
        if self._nb_drones is not None:
            self._error(line_number, "nb_drones may only be declared once")
        if metadata is not None:
            self._error(line_number, "nb_drones does not accept metadata")
        self._nb_drones = self._positive_integer(
            value, "nb_drones", line_number
        )

    def _parse_hub(
        self,
        hub_type: str,
        value: str,
        metadata_text: str | None,
        line_number: int,
    ) -> None:
        """Parse and validate a zone declaration."""
        parts = value.split()
        if len(parts) != 3:
            self._error(
                line_number,
                f"{hub_type} requires exactly '<name> <x> <y>'",
            )

        name, x_text, y_text = parts
        self._validate_zone_name(name, line_number)
        if name in self._zone_lines:
            original_line = self._zone_lines[name]
            self._error(
                line_number,
                f"duplicate zone '{name}' (first declared on line "
                f"{original_line})",
            )

        metadata = self._parse_metadata(
            metadata_text,
            self._ZONE_METADATA,
            "zone",
            line_number,
        )
        kind = metadata.get("zone", "normal")
        if kind not in self._ZONE_TYPES:
            allowed = ", ".join(sorted(self._ZONE_TYPES))
            self._error(
                line_number,
                f"invalid zone type '{kind}'; expected one of: {allowed}",
            )

        parsed_max_drones = self._optional_positive_integer(
            metadata, "max_drones", 1, line_number
        )
        # The current subject states that start and end hubs are unlimited even
        # if a max_drones metadata value is present, so keep a neutral stored
        # value instead of preserving an ignored limit.
        max_drones = (
            1
            if hub_type in {"start_hub", "end_hub"}
            else parsed_max_drones
        )
        color = metadata.get("color")
        if color == "":
            self._error(line_number, "metadata 'color' cannot be empty")

        hub_data: HubData = {
            "name": name,
            "kind": kind,
            "x": self._integer(x_text, "x coordinate", line_number),
            "y": self._integer(y_text, "y coordinate", line_number),
            "is_start": hub_type == "start_hub",
            "is_end": hub_type == "end_hub",
            "color": color,
            "max_drones": max_drones,
        }
        self._hubs.append(hub_data)
        self._zone_lines[name] = line_number
        if hub_data["is_start"]:
            self._start_lines.append(line_number)
        if hub_data["is_end"]:
            self._end_lines.append(line_number)

    def _parse_connection(
        self,
        value: str,
        metadata_text: str | None,
        line_number: int,
    ) -> None:
        """Parse and validate an undirected connection declaration."""
        if value.count("-") != 1:
            self._error(
                line_number,
                "connection requires exactly '<zone1>-<zone2>'",
            )
        from_name, to_name = value.split("-")
        if not from_name or not to_name:
            self._error(line_number, "connection zone names cannot be empty")
        if from_name != from_name.strip() or to_name != to_name.strip():
            self._error(
                line_number,
                "connection zone names cannot contain spaces",
            )
        if from_name == to_name:
            self._error(line_number, "a zone cannot connect to itself")

        for zone_name in (from_name, to_name):
            if zone_name not in self._zone_lines:
                self._error(
                    line_number,
                    f"connection references zone '{zone_name}' before its "
                    "declaration",
                )

        connection_key = frozenset({from_name, to_name})
        if connection_key in self._connection_lines:
            original_line = self._connection_lines[connection_key]
            self._error(
                line_number,
                f"duplicate connection '{from_name}-{to_name}' (first "
                f"declared on line {original_line})",
            )

        metadata = self._parse_metadata(
            metadata_text,
            self._CONNECTION_METADATA,
            "connection",
            line_number,
        )
        max_capacity = self._optional_positive_integer(
            metadata, "max_link_capacity", 1, line_number
        )
        self._connections.append(
            {
                "from": from_name,
                "to": to_name,
                "max_link_capacity": max_capacity,
            }
        )
        self._connection_lines[connection_key] = line_number

    def _parse_metadata(
        self,
        metadata_text: str | None,
        allowed_keys: frozenset[str],
        owner: str,
        line_number: int,
    ) -> dict[str, str]:
        """Parse a complete metadata block without ignoring invalid tokens."""
        if metadata_text is None:
            return {}

        metadata: dict[str, str] = {}
        for token in metadata_text.split():
            if token.count("=") != 1:
                self._error(
                    line_number,
                    f"invalid metadata token '{token}'; expected key=value",
                )
            key, value = token.split("=", maxsplit=1)
            if self._METADATA_KEY_PATTERN.fullmatch(key) is None or not value:
                self._error(line_number, f"invalid metadata token '{token}'")
            if key not in allowed_keys:
                self._error(
                    line_number,
                    f"metadata '{key}' is not valid for a {owner}",
                )
            if key in metadata:
                self._error(line_number, f"duplicate metadata key '{key}'")
            metadata[key] = value
        return metadata

    def _validate_zone_name(self, name: str, line_number: int) -> None:
        """Validate the subject's restrictions for zone names."""
        if "-" in name or any(character.isspace() for character in name):
            self._error(
                line_number,
                f"invalid zone name '{name}'; dashes and spaces are forbidden",
            )

    def _validate_required_declarations(self) -> None:
        """Ensure the map contains each required unique declaration."""
        if self._nb_drones is None:
            self._error(1, "nb_drones is required")
        if len(self._start_lines) != 1:
            self._error(
                self._start_lines[-1] if self._start_lines else 1,
                "exactly one start_hub is required "
                f"(found {len(self._start_lines)})",
            )
        if len(self._end_lines) != 1:
            end_count = len(self._end_lines)
            self._error(
                self._end_lines[-1] if self._end_lines else 1,
                f"exactly one end_hub is required (found {end_count})",
            )

    def _optional_positive_integer(
        self,
        metadata: dict[str, str],
        key: str,
        default: int,
        line_number: int,
    ) -> int:
        """Read an optional positive integer metadata value."""
        value = metadata.get(key)
        if value is None:
            return default
        return self._positive_integer(value, key, line_number)

    def _positive_integer(
        self, value: str, field: str, line_number: int
    ) -> int:
        """Convert a decimal string to a strictly positive integer."""
        if self._POSITIVE_INTEGER_PATTERN.fullmatch(value) is None:
            self._error(line_number, f"{field} must be a positive integer")
        parsed_value = int(value)
        if parsed_value <= 0:
            self._error(line_number, f"{field} must be greater than zero")
        return parsed_value

    def _integer(self, value: str, field: str, line_number: int) -> int:
        """Convert a coordinate to an integer."""
        try:
            return int(value)
        except ValueError as error:
            raise ValueError(
                f"Line {line_number}: {field} must be an integer"
            ) from error

    @staticmethod
    def _error(line_number: int, cause: str) -> NoReturn:
        """Raise a consistently formatted, line-aware parsing error."""
        raise ValueError(f"Line {line_number}: {cause}")
