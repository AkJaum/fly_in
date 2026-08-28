"""UI-independent presentation helpers for the Fly-in simulation."""

import hashlib
import html
import math
import re
from dataclasses import dataclass
from pathlib import Path

from src.drone import Drone
from src.fly_in import Simulation
from src.ZoneHub import Connection, Zone


@dataclass(frozen=True)
class DroneLocation:
    """Identify one physical drone location in the simulation graph."""

    kind: str
    name: str

    @property
    def label(self) -> str:
        """Return a concise location label for visual descriptions."""
        if self.kind == "connection":
            return f"connection {self.name}"
        return f"zone {self.name}"


@dataclass(frozen=True)
class DroneTransition:
    """Describe one observed drone movement between two visual states."""

    drone_id: str
    origin: DroneLocation
    destination: DroneLocation
    status: str


@dataclass(frozen=True)
class SimulationSnapshot:
    """Describe the simulation values displayed by a visual interface."""

    map_name: str
    turn: int
    total_drones: int
    active_drones: int
    delivered_drones: int
    in_transit_drones: int
    moved_drones: int
    waiting_drones: int
    last_movement: str
    is_complete: bool


class BrowserSimulation:
    """Expose the simulation lifecycle without coupling it to a UI toolkit."""

    def __init__(
        self,
        project_root: Path,
        output_file: Path,
        initial_map: Path | None = None,
    ) -> None:
        """Discover project maps and prepare an unloaded simulation."""
        self.project_root = project_root.resolve()
        self.output_file = output_file.resolve()
        resolved_initial_map = initial_map.resolve() if initial_map else None
        self.available_maps = self._discover_maps(resolved_initial_map)
        self.selected_map = (
            self._map_name(resolved_initial_map)
            if resolved_initial_map
            else next(iter(self.available_maps))
        )
        self.simulation: Simulation | None = None
        self.last_movement = "No movement has been executed yet."
        self.last_transitions: tuple[DroneTransition, ...] = ()

    def configure(self, map_name: str | None = None) -> None:
        """Load one known map and reset its complete simulation state."""
        selected_map = map_name or self.selected_map
        map_path = self.available_maps.get(selected_map)
        if map_path is None:
            raise ValueError(f"Unknown project map: {selected_map}")

        simulation = Simulation(str(map_path), str(self.output_file))
        simulation.configure()
        self.selected_map = selected_map
        self.simulation = simulation
        self.last_movement = "Map loaded. Press Step or Play to begin."
        self.last_transitions = ()

    def step(self) -> str:
        """Execute one turn and retain its exact visual transitions."""
        if self.simulation is None:
            self.configure()
        simulation = self._configured_simulation()
        if not simulation.active_drones:
            return ""

        before = {
            drone.id: self._drone_location(drone)
            for drone in simulation.drones
        }
        movement = simulation.next_turn()
        transitions: list[DroneTransition] = []
        for drone in simulation.drones:
            transition = self._transition_for(
                drone,
                before[drone.id],
                simulation,
            )
            if transition is not None:
                transitions.append(transition)
        self.last_transitions = tuple(transitions)
        self.last_movement = movement
        return movement

    def reset(self) -> None:
        """Reload the selected map from its initial state."""
        self.configure(self.selected_map)

    def snapshot(self) -> SimulationSnapshot:
        """Return immutable values for status cards and controls."""
        simulation = self._configured_simulation()
        active_drones = len(simulation.active_drones)
        moved_active_ids = {
            transition.drone_id
            for transition in self.last_transitions
            if not self._is_delivered(transition, simulation)
        }
        waiting_drones = 0
        if simulation.turn_number:
            waiting_drones = max(active_drones - len(moved_active_ids), 0)
        return SimulationSnapshot(
            map_name=self.selected_map,
            turn=simulation.turn_number,
            total_drones=simulation.nb_drones,
            active_drones=active_drones,
            delivered_drones=simulation.nb_drones - active_drones,
            in_transit_drones=sum(
                drone.in_transit is not None for drone in simulation.drones
            ),
            moved_drones=len(self.last_transitions),
            waiting_drones=waiting_drones,
            last_movement=self.last_movement,
            is_complete=not simulation.active_drones,
        )

    def drone_locations(self) -> tuple[tuple[str, DroneLocation, str], ...]:
        """Return every drone location and its current lifecycle state."""
        simulation = self._configured_simulation()
        values: list[tuple[str, DroneLocation, str]] = []
        for drone in simulation.drones:
            location = self._drone_location(drone)
            if drone.finished_traversal:
                state = "delivered"
            elif drone.in_transit is not None:
                state = "in transit (turn 1 of 2)"
            else:
                state = "active"
            values.append((drone.id, location, state))
        return tuple(values)

    def simulation_or_raise(self) -> Simulation:
        """Return the configured simulation for rendering."""
        return self._configured_simulation()

    def _discover_maps(
        self,
        initial_map: Path | None,
    ) -> dict[str, Path]:
        """Return root and benchmark map files in deterministic order."""
        candidates: list[Path] = []
        if initial_map is not None:
            if not initial_map.is_file():
                raise ValueError(f"Initial map file not found: {initial_map}")
            candidates.append(initial_map)
        default_map = self.project_root / "map.txt"
        if default_map.is_file() and default_map not in candidates:
            candidates.append(default_map)

        maps_directory = self.project_root / "maps"
        if maps_directory.is_dir():
            candidates.extend(
                path
                for path in sorted(maps_directory.rglob("*.txt"))
                if path not in candidates
            )

        if not candidates:
            raise ValueError("No Fly-in map files were found")
        return {self._map_name(path): path for path in candidates}

    def _map_name(self, path: Path) -> str:
        """Return a stable label for project or external map files."""
        try:
            return path.relative_to(self.project_root).as_posix()
        except ValueError:
            return f"external: {path}"

    @staticmethod
    def _drone_location(drone: Drone) -> DroneLocation:
        """Resolve a drone to a zone or an occupied connection."""
        if drone.current_zone is not None:
            return DroneLocation("zone", drone.current_zone.name)
        if drone.in_transit is not None:
            return DroneLocation("connection", drone.in_transit.name)
        raise RuntimeError(f"Drone {drone.id} has no visual location")

    def _transition_for(
        self,
        drone: Drone,
        origin: DroneLocation,
        simulation: Simulation,
    ) -> DroneTransition | None:
        """Build a transition only when a drone changed physical location."""
        destination = self._drone_location(drone)
        if origin == destination:
            return None
        if destination.kind == "connection":
            status = "restricted transit: turn 1 of 2"
        elif origin.kind == "connection":
            status = "restricted arrival: turn 2 of 2"
        else:
            status = "moved"
        transition = DroneTransition(
            drone.id,
            origin,
            destination,
            status,
        )
        if self._is_delivered(transition, simulation):
            return DroneTransition(
                drone.id,
                origin,
                destination,
                "delivered",
            )
        return transition

    @staticmethod
    def _is_delivered(
        transition: DroneTransition,
        simulation: Simulation,
    ) -> bool:
        """Return whether a transition finishes at the configured end zone."""
        end_zone = simulation.graph.end_zone
        return (
            end_zone is not None
            and transition.destination.kind == "zone"
            and transition.destination.name == end_zone.name
        )

    def _configured_simulation(self) -> Simulation:
        """Return the active simulation or report an invalid lifecycle."""
        if self.simulation is None:
            raise RuntimeError("The browser simulation is not configured")
        return self.simulation


class SvgMapRenderer:
    """Render graph state as safe, dependency-free browser SVG markup."""

    MIN_WIDTH = 1000.0
    MIN_HEIGHT = 600.0
    HORIZONTAL_GAP = 170.0
    VERTICAL_GAP = 170.0
    HORIZONTAL_PADDING = 150.0
    VERTICAL_PADDING = 130.0
    TARGET_ASPECT_RATIO = 2.25
    ZONE_RADIUS = 39.0
    DRONE_SCREEN_GAP = 42.0
    DRONE_RING_GAP = 34.0
    MAX_DRONE_MARKERS = 16
    _SAFE_COLOR = re.compile(r"^[A-Za-z]+$")
    _KIND_COLORS = {
        "normal": "#38bdf8",
        "priority": "#22c55e",
        "restricted": "#f97316",
        "blocked": "#64748b",
    }

    def render(
        self,
        simulation: Simulation,
        transitions: tuple[DroneTransition, ...] = (),
    ) -> str:
        """Build an SVG showing the graph, drones, and latest movement."""
        zones = list(simulation.graph.zones.values())
        if not zones:
            return self._empty_svg("No configured graph")

        positions, canvas = self._adaptive_layout(zones)
        canvas_x, canvas_y, canvas_width, canvas_height = canvas
        layout_key = self._layout_key(zones, canvas)
        highlighted_connections = {
            location.name
            for transition in transitions
            for location in (transition.origin, transition.destination)
            if location.kind == "connection"
        }
        highlighted_zones = {
            transition.destination.name
            for transition in transitions
            if transition.destination.kind == "zone"
        }
        complexity_class = " map-complex" if (
            len(zones) > 12 or len(simulation.graph.connections) > 18
        ) else ""
        transition_offsets = self._transition_offsets(transitions)
        parts = [
            f'<svg class="flyin-map{complexity_class}" '
            f'viewBox="{canvas_x:.1f} {canvas_y:.1f} '
            f'{canvas_width:.1f} {canvas_height:.1f}" '
            f'data-base-x="{canvas_x:.1f}" '
            f'data-base-y="{canvas_y:.1f}" '
            f'data-base-width="{canvas_width:.1f}" '
            f'data-base-height="{canvas_height:.1f}" '
            f'data-layout-key="{layout_key}" '
            'preserveAspectRatio="xMidYMid meet" role="img" '
            'aria-label="Zoomable Fly-in live drone network">',
            self._definitions(),
            f'<rect x="{canvas_x:.1f}" y="{canvas_y:.1f}" '
            f'width="{canvas_width:.1f}" height="{canvas_height:.1f}" '
            'rx="24" '
            'fill="url(#canvas-grid)"/>',
            self._turn_banner(simulation, transitions),
            '<g class="map-world"><g class="connections">',
        ]
        for connection in simulation.graph.connections:
            parts.append(
                self._connection_markup(
                    connection,
                    positions,
                    connection.name in highlighted_connections,
                )
            )
        parts.append('</g><g class="zones">')
        for zone in zones:
            parts.append(
                self._zone_markup(
                    zone,
                    positions[zone],
                    zone.name in highlighted_zones,
                )
            )
        parts.append('</g><g class="drones">')
        parts.extend(
            self._all_drone_markers(simulation, positions, transitions)
        )
        parts.append('</g><g class="movement-overlay">')
        parts.extend(
            self._transition_markup(
                transition,
                simulation,
                positions,
                transition_offsets[index],
            )
            for index, transition in enumerate(transitions)
        )
        parts.append("</g></g></svg>")
        return "".join(parts)

    @staticmethod
    def _definitions() -> str:
        """Return SVG paint, arrow, and glow definitions."""
        return (
            '<defs><linearGradient id="rainbow-zone" x1="0" y1="0" '
            'x2="1" y2="1"><stop offset="0" stop-color="#ef4444"/>'
            '<stop offset=".33" stop-color="#facc15"/>'
            '<stop offset=".66" stop-color="#22c55e"/>'
            '<stop offset="1" stop-color="#3b82f6"/></linearGradient>'
            '<marker id="movement-arrow" markerWidth="10" markerHeight="10" '
            'refX="7" refY="3" orient="auto" markerUnits="strokeWidth">'
            '<path d="M0,0 L0,6 L8,3 z" fill="#67e8f9"/></marker>'
            '<filter id="drone-glow" x="-60%" y="-60%" width="220%" '
            'height="220%"><feGaussianBlur stdDeviation="4" '
            'result="blur"/><feMerge><feMergeNode in="blur"/>'
            '<feMergeNode in="SourceGraphic"/></feMerge></filter>'
            '<pattern id="canvas-grid" width="32" height="32" '
            'patternUnits="userSpaceOnUse"><rect width="32" height="32" '
            'fill="#07111f"/><circle cx="1" cy="1" r="1.2" '
            'fill="#1e3a52" opacity="0.75"/></pattern>'
            '<marker id="transit-arrow" markerWidth="10" '
            'markerHeight="10" refX="7" refY="3" orient="auto" '
            'markerUnits="strokeWidth"><path d="M0,0 L0,6 L8,3 z" '
            'fill="#facc15"/></marker></defs>'
        )

    @staticmethod
    def _turn_banner(
        simulation: Simulation,
        transitions: tuple[DroneTransition, ...],
    ) -> str:
        """Render a persistent explanation of the current visual state."""
        delivered = simulation.nb_drones - len(simulation.active_drones)
        return (
            '<text x="36" y="42" class="map-caption">'
            f'Turn {simulation.turn_number} · {len(transitions)} moved · '
            f'{delivered}/{simulation.nb_drones} delivered</text>'
        )

    def _adaptive_layout(
        self,
        zones: list[Zone],
    ) -> tuple[
        dict[Zone, tuple[float, float]],
        tuple[float, float, float, float],
    ]:
        """Preserve map geometry while guaranteeing readable node spacing."""
        x_values = [zone.pos[0] for zone in zones]
        y_values = [zone.pos[1] for zone in zones]
        minimum_x, maximum_x = min(x_values), max(x_values)
        minimum_y, maximum_y = min(y_values), max(y_values)
        x_span = maximum_x - minimum_x
        y_span = maximum_y - minimum_y

        horizontal_gap = self.HORIZONTAL_GAP
        vertical_gap = self.VERTICAL_GAP
        if x_span and y_span:
            content_width = x_span * horizontal_gap
            required_height = content_width / self.TARGET_ASPECT_RATIO
            vertical_gap = max(vertical_gap, required_height / y_span)

        content_width = x_span * horizontal_gap
        content_height = y_span * vertical_gap
        canvas_width = max(
            self.MIN_WIDTH,
            content_width + 2 * self.HORIZONTAL_PADDING,
        )
        canvas_height = max(
            self.MIN_HEIGHT,
            content_height + 2 * self.VERTICAL_PADDING,
        )
        left = (canvas_width - content_width) / 2
        bottom = (canvas_height + content_height) / 2
        positions = {
            zone: (
                canvas_width / 2
                if x_span == 0
                else left + (zone.pos[0] - minimum_x) * horizontal_gap,
                canvas_height / 2
                if y_span == 0
                else bottom - (zone.pos[1] - minimum_y) * vertical_gap,
            )
            for zone in zones
        }
        return positions, (0.0, 0.0, canvas_width, canvas_height)

    @staticmethod
    def _layout_key(
        zones: list[Zone],
        canvas: tuple[float, float, float, float],
    ) -> str:
        """Return a stable key so turn refreshes can preserve the camera."""
        signature = "|".join(
            f"{zone.name}:{zone.pos[0]}:{zone.pos[1]}"
            for zone in zones
        )
        signature += ":" + ":".join(f"{value:.1f}" for value in canvas)
        return hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]

    def _connection_markup(
        self,
        connection: Connection,
        positions: dict[Zone, tuple[float, float]],
        highlighted: bool,
    ) -> str:
        """Render one labelled connection and its current capacity usage."""
        start_x, start_y = positions[connection.previous_zone]
        end_x, end_y = positions[connection.next_zone]
        midpoint_x = (start_x + end_x) / 2
        midpoint_y = (start_y + end_y) / 2
        name = html.escape(connection.name, quote=True)
        usage = len(connection.drones_in)
        capacity = connection.max_link_capacity
        stroke = "#67e8f9" if highlighted else "#334155"
        width = "9" if highlighted else "7"
        transit = ""
        if usage:
            transit = (
                f'<circle cx="{midpoint_x:.1f}" cy="{midpoint_y:.1f}" '
                'r="24" fill="#facc15" stroke="#07111f" '
                'stroke-width="5" class="transit-location"/>'
                f'<text x="{midpoint_x:.1f}" y="{midpoint_y + 5:.1f}" '
                'text-anchor="middle" class="transit-count">'
                f'{usage}/{capacity}</text>'
            )
        return (
            f'<g class="connection-node"><title>{name}: '
            f'{usage}/{capacity} in transit</title>'
            f'<line x1="{start_x:.1f}" y1="{start_y:.1f}" '
            f'x2="{end_x:.1f}" y2="{end_y:.1f}" '
            f'stroke="{stroke}" stroke-width="{width}" '
            'stroke-linecap="round"/>'
            f'<rect x="{midpoint_x - 31:.1f}" y="{midpoint_y - 35:.1f}" '
            'width="62" height="22" rx="11" fill="#07111f" '
            'stroke="#334155" stroke-width="1" '
            'class="connection-badge"/>'
            f'<text x="{midpoint_x:.1f}" y="{midpoint_y - 17:.1f}" '
            'text-anchor="middle" class="connection-label">'
            f'link {usage}/{capacity}</text>{transit}</g>'
        )

    def _zone_markup(
        self,
        zone: Zone,
        position: tuple[float, float],
        highlighted: bool,
    ) -> str:
        """Render one zone with type, metadata color, and occupancy."""
        x_position, y_position = position
        name = html.escape(zone.name, quote=True)
        kind = html.escape(zone.kind, quote=True)
        color = self._display_color(zone)
        color_name = html.escape(zone.color or "type default", quote=True)
        occupancy = len(zone.drones_in)
        capacity = "∞" if zone.is_start or zone.is_end else str(
            zone.max_drones
        )
        rings = ""
        if zone.is_start or zone.is_end:
            rings += (
                f'<circle cx="{x_position:.1f}" cy="{y_position:.1f}" '
                'r="48" fill="none" stroke="#e2e8f0" '
                'stroke-width="3" opacity="0.7"/>'
            )
        if highlighted:
            rings += (
                f'<circle cx="{x_position:.1f}" cy="{y_position:.1f}" '
                'r="55" fill="none" stroke="#67e8f9" stroke-width="5" '
                'class="destination-pulse"/>'
            )
        type_symbol = {
            "priority": "P",
            "restricted": "R",
            "blocked": "X",
            "normal": "N",
        }.get(zone.kind, "?")
        endpoint = "START" if zone.is_start else "END" if zone.is_end else ""
        endpoint_class = " zone-endpoint" if endpoint else ""
        shape = self._zone_shape_markup(
            zone,
            x_position,
            y_position,
            color,
        )
        return (
            f'<g class="zone-node{endpoint_class}"><title>{name}: {kind}; '
            f'{occupancy}/{capacity} drones; '
            f'color={color_name}</title>{rings}'
            f'{shape}'
            f'<text x="{x_position:.1f}" y="{y_position + 7:.1f}" '
            f'text-anchor="middle" class="type-symbol">{type_symbol}</text>'
            f'<text x="{x_position:.1f}" y="{y_position + 67:.1f}" '
            f'text-anchor="middle" class="zone-label">{name}</text>'
            f'<text x="{x_position:.1f}" y="{y_position + 87:.1f}" '
            f'text-anchor="middle" class="zone-detail">{endpoint or kind} · '
            f'{occupancy}/{capacity} · {color_name}</text></g>'
        )

    @staticmethod
    def _zone_shape_markup(
        zone: Zone,
        x_position: float,
        y_position: float,
        color: str,
    ) -> str:
        """Render a distinct silhouette for every zone behavior."""
        common = f'fill="{color}" stroke="#f8fafc" stroke-width="4"'
        if zone.kind == "priority":
            points = (
                f"{x_position:.1f},{y_position - 43:.1f} "
                f"{x_position + 38:.1f},{y_position - 21:.1f} "
                f"{x_position + 38:.1f},{y_position + 21:.1f} "
                f"{x_position:.1f},{y_position + 43:.1f} "
                f"{x_position - 38:.1f},{y_position + 21:.1f} "
                f"{x_position - 38:.1f},{y_position - 21:.1f}"
            )
            return f'<polygon points="{points}" {common}/>'
        if zone.kind == "restricted":
            return (
                f'<rect x="{x_position - 31:.1f}" '
                f'y="{y_position - 31:.1f}" width="62" height="62" '
                f'rx="8" transform="rotate(45 {x_position:.1f} '
                f'{y_position:.1f})" {common}/>'
            )
        if zone.kind == "blocked":
            return (
                f'<rect x="{x_position - 39:.1f}" '
                f'y="{y_position - 39:.1f}" width="78" height="78" '
                f'rx="8" {common} stroke-dasharray="7 5"/>'
                f'<path d="M {x_position - 24:.1f} {y_position - 24:.1f} '
                f'L {x_position + 24:.1f} {y_position + 24:.1f} '
                f'M {x_position + 24:.1f} {y_position - 24:.1f} '
                f'L {x_position - 24:.1f} {y_position + 24:.1f}" '
                'stroke="#07111f" stroke-width="8" '
                'stroke-linecap="round" opacity="0.65"/>'
            )
        return (
            f'<circle cx="{x_position:.1f}" cy="{y_position:.1f}" '
            f'r="39" {common}/>'
        )

    def _all_drone_markers(
        self,
        simulation: Simulation,
        positions: dict[Zone, tuple[float, float]],
        transitions: tuple[DroneTransition, ...],
    ) -> list[str]:
        """Render identifiable markers at every current drone location."""
        parts: list[str] = []
        moved_ids = {transition.drone_id for transition in transitions}
        drone_states: dict[str, str] = {}
        for drone in simulation.drones:
            if drone.finished_traversal:
                state = "delivered"
            elif drone.in_transit is not None:
                state = "transit"
            elif drone.id in moved_ids:
                state = "moved"
            elif simulation.turn_number:
                state = "waiting"
            else:
                state = "zone"
            if drone.id in moved_ids and state != "moved":
                state += " drone-moved"
            drone_states[drone.id] = state
        for zone in simulation.graph.zones.values():
            parts.extend(
                self._location_drone_markers(
                    zone.drones_in,
                    positions[zone],
                    drone_states,
                    zone.name,
                )
            )
        for connection in simulation.graph.connections:
            if not connection.drones_in:
                continue
            start = positions[connection.previous_zone]
            end = positions[connection.next_zone]
            midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            parts.extend(
                self._location_drone_markers(
                    connection.drones_in,
                    midpoint,
                    drone_states,
                    connection.name,
                )
            )
        return parts

    def _location_drone_markers(
        self,
        drones: list[Drone],
        center: tuple[float, float],
        drone_states: dict[str, str],
        location_name: str,
    ) -> list[str]:
        """Anchor one zoom-aware drone cluster to a graph location."""
        if not drones:
            return []
        x_position, y_position = center
        safe_location = html.escape(location_name, quote=True)
        parts = [
            f'<g class="drone-cluster" '
            f'transform="translate({x_position:.1f} {y_position:.1f})" '
            f'data-anchor-x="{x_position:.1f}" '
            f'data-anchor-y="{y_position:.1f}">'
            f'<title>{len(drones)} drones at {safe_location}</title>'
            '<g class="occupancy-summary screen-fixed-marker" '
            'data-offset-x="48" data-offset-y="-48" '
            'transform="translate(48 -48)">'
            '<circle r="19" fill="#e2e8f0" stroke="#07111f" '
            'stroke-width="4"/>'
            f'<text x="0" y="5" text-anchor="middle" '
            f'class="overflow-count">{len(drones)}</text></g>'
        ]
        visible_drones = drones[:self.MAX_DRONE_MARKERS]
        for index, drone in enumerate(visible_drones):
            orbit_x, orbit_y, ring = self._marker_orbit(
                index,
                len(visible_drones),
            )
            parts.append(
                self._drone_marker(
                    drone.id,
                    orbit_x,
                    orbit_y,
                    ring,
                    drone_states[drone.id],
                    f"{drone.id} at {location_name}",
                )
            )
        hidden_count = len(drones) - len(visible_drones)
        if hidden_count:
            parts.append(
                '<g class="occupancy-overflow screen-fixed-marker" '
                'data-offset-x="64" data-offset-y="42" '
                'transform="translate(64 42)"><title>'
                f'{hidden_count} additional drones at '
                f'{safe_location}</title>'
                '<rect x="-26" y="-13" width="52" height="25" '
                'rx="12" fill="#e2e8f0"/>'
                '<text x="0" y="5" text-anchor="middle" '
                'class="overflow-count">'
                f'+{hidden_count}</text></g>'
            )
        parts.append("</g>")
        return parts

    @staticmethod
    def _marker_orbit(
        index: int,
        total: int,
    ) -> tuple[float, float, int]:
        """Return a deterministic direction and ring for a drone marker."""
        ring = 0 if total <= 10 else index // 10
        orbit_index = index if total <= 10 else index % 10
        orbit_size = total if total <= 10 else min(10, total)
        angle = -math.pi / 2 + 2 * math.pi * orbit_index / orbit_size
        return math.cos(angle), math.sin(angle), ring

    @classmethod
    def _drone_marker(
        cls,
        drone_id: str,
        orbit_x: float,
        orbit_y: float,
        ring: int,
        state: str,
        title: str,
    ) -> str:
        """Return one marker whose local orbit follows the camera zoom."""
        safe_id = html.escape(drone_id, quote=True)
        safe_title = html.escape(title, quote=True)
        radius = (
            cls.ZONE_RADIUS
            + cls.DRONE_SCREEN_GAP
            + ring * cls.DRONE_RING_GAP
        )
        x_position = orbit_x * radius
        y_position = orbit_y * radius
        return (
            f'<g class="drone-marker drone-{state}" '
            f'data-orbit-x="{orbit_x:.6f}" '
            f'data-orbit-y="{orbit_y:.6f}" data-ring="{ring}" '
            f'transform="translate({x_position:.1f} {y_position:.1f})">'
            f'<title>{safe_title}</title>'
            f'{SvgMapRenderer._drone_shape_markup(safe_id)}</g>'
        )

    @staticmethod
    def _drone_shape_markup(drone_id: str) -> str:
        """Return a recognizable quadcopter silhouette with status light."""
        return (
            '<g class="drone-silhouette">'
            '<path d="M-8,-5 L-18,-13 M8,-5 L18,-13 '
            'M-8,5 L-18,13 M8,5 L18,13" class="drone-arm"/>'
            '<ellipse cx="-20" cy="-14" rx="7" ry="3" '
            'class="drone-rotor"/>'
            '<ellipse cx="20" cy="-14" rx="7" ry="3" '
            'class="drone-rotor"/>'
            '<ellipse cx="-20" cy="14" rx="7" ry="3" '
            'class="drone-rotor"/>'
            '<ellipse cx="20" cy="14" rx="7" ry="3" '
            'class="drone-rotor"/>'
            '<path d="M-10,-7 Q0,-14 10,-7 L12,6 Q0,13 -12,6 Z" '
            'class="drone-body"/>'
            '<path d="M-5,-8 L0,-14 L5,-8" fill="#e2e8f0" '
            'stroke="#07111f" stroke-width="1.5"/>'
            '<circle cx="0" cy="1" r="4" '
            'class="drone-status-light"/>'
            '<rect x="-14" y="18" width="28" height="15" rx="7.5" '
            'class="drone-id-plate"/>'
            f'<text x="0" y="29" text-anchor="middle" '
            f'class="drone-id">{drone_id}</text></g>'
        )

    def _transition_markup(
        self,
        transition: DroneTransition,
        simulation: Simulation,
        positions: dict[Zone, tuple[float, float]],
        lane_offset: float,
    ) -> str:
        """Animate one staged movement on its own readable route lane."""
        start_x, start_y = self._location_position(
            transition.origin,
            simulation,
            positions,
        )
        end_x, end_y = self._location_position(
            transition.destination,
            simulation,
            positions,
        )
        delta_x = end_x - start_x
        delta_y = end_y - start_y
        distance = math.hypot(delta_x, delta_y)
        if distance:
            start_x += -delta_y / distance * lane_offset
            start_y += delta_x / distance * lane_offset
            end_x += -delta_y / distance * lane_offset
            end_y += delta_x / distance * lane_offset
        drone_id = html.escape(transition.drone_id, quote=True)
        status = html.escape(transition.status, quote=True)
        path = f"M {start_x:.1f} {start_y:.1f} L {end_x:.1f} {end_y:.1f}"
        is_restricted_step = (
            transition.origin.kind == "connection"
            or transition.destination.kind == "connection"
        )
        trace_color = "#facc15" if is_restricted_step else "#67e8f9"
        arrow = "transit-arrow" if is_restricted_step else "movement-arrow"
        flight_class = " restricted-flight" if is_restricted_step else ""
        return (
            f'<g class="movement-trace"><title>{drone_id}: {status}</title>'
            f'<circle cx="{start_x:.1f}" cy="{start_y:.1f}" r="8" '
            f'fill="none" stroke="{trace_color}" stroke-width="4" '
            'class="departure-beacon"/>'
            f'<path d="{path}" fill="none" stroke="{trace_color}" '
            'stroke-width="4" stroke-dasharray="10 8" '
            f'marker-end="url(#{arrow})" class="movement-path"/>'
            f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="8" '
            f'fill="none" stroke="{trace_color}" stroke-width="5" '
            'class="arrival-beacon"/>'
            f'<g class="animated-drone{flight_class}">'
            f'{self._drone_shape_markup(drone_id)}'
            f'<animateMotion begin="0.2s" dur="0.82s" path="{path}" '
            'fill="freeze" '
            'calcMode="spline" keySplines="0.4 0 0.2 1"/></g></g>'
        )

    @staticmethod
    def _transition_offsets(
        transitions: tuple[DroneTransition, ...],
    ) -> list[float]:
        """Assign parallel lanes to simultaneous moves sharing one route."""
        groups: dict[
            tuple[tuple[str, str], tuple[str, str]],
            list[int],
        ] = {}
        for index, transition in enumerate(transitions):
            origin = (transition.origin.kind, transition.origin.name)
            destination = (
                transition.destination.kind,
                transition.destination.name,
            )
            route = (
                (origin, destination)
                if origin <= destination
                else (destination, origin)
            )
            groups.setdefault(route, []).append(index)

        offsets = [0.0] * len(transitions)
        for indexes in groups.values():
            midpoint = (len(indexes) - 1) / 2
            spacing = min(18.0, 84.0 / max(len(indexes) - 1, 1))
            for lane, transition_index in enumerate(indexes):
                offsets[transition_index] = (lane - midpoint) * spacing
        return offsets

    @staticmethod
    def _location_position(
        location: DroneLocation,
        simulation: Simulation,
        positions: dict[Zone, tuple[float, float]],
    ) -> tuple[float, float]:
        """Resolve a visual location into scaled SVG coordinates."""
        if location.kind == "zone":
            zone = simulation.graph.zones.get(location.name)
            if zone is None:
                raise RuntimeError(f"Unknown visual zone: {location.name}")
            return positions[zone]
        for connection in simulation.graph.connections:
            if connection.name == location.name:
                start = positions[connection.previous_zone]
                end = positions[connection.next_zone]
                return ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        raise RuntimeError(f"Unknown visual connection: {location.name}")

    def _display_color(self, zone: Zone) -> str:
        """Use named metadata colors, including the supplied rainbow value."""
        if zone.color == "rainbow":
            return "url(#rainbow-zone)"
        if zone.color and self._SAFE_COLOR.fullmatch(zone.color):
            return zone.color
        return self._KIND_COLORS.get(zone.kind, self._KIND_COLORS["normal"])

    @staticmethod
    def _empty_svg(message: str) -> str:
        """Return a small SVG placeholder for an empty state."""
        safe_message = html.escape(message)
        return (
            '<svg class="flyin-map" viewBox="0 0 1000 600" '
            'data-base-x="0" data-base-y="0" data-base-width="1000" '
            'data-base-height="600" data-layout-key="empty" role="img">'
            '<rect width="1000" height="600" rx="24" fill="#07111f"/>'
            '<text x="500" y="300" text-anchor="middle" '
            f'class="empty-label">{safe_message}</text></svg>'
        )
