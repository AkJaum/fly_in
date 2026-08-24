*This project has been created as part of the 42 curriculum by jneris-d.*

# Fly-in

## Description

Fly-in is a Python 3 drone-routing simulator. It receives a map that describes
zones, connections, capacities, zone types, and a fleet size, then simulates the
movement of all drones from a start hub to an end hub.

The goal of the project is to move every drone to the end hub in the fewest
possible simulation turns while respecting:

- unlimited occupancy on the start and end hubs, even if `max_drones`
  metadata is present there;
- zone capacities through `max_drones`;
- connection capacities through `max_link_capacity`;
- blocked zones, which cannot be entered;
- restricted zones, which take two turns to enter;
- priority zones, which are preferred by the pathfinder;
- simultaneous movement conflicts.

The implementation must be object-oriented and split into parser, graph,
domain, drone, and simulation layers.

## Current Status

Implemented and working:

- map parsing with line-aware validation errors;
- support for comments and optional metadata blocks;
- validation for unique start/end hubs, duplicate zones, duplicate undirected
  connections, positive capacities, valid coordinates, and valid zone types;
- graph construction without graph helper libraries;
- drone identifiers in the `D1`, `D2`, ... format;
- Dijkstra-based pathfinding implemented in the project;
- blocked-zone avoidance;
- priority-zone preference through lower pathfinding weight;
- restricted-zone movement as a two-turn transition through the connection;
- turn-by-turn simultaneous movement resolution;
- global capacity-aware route distribution with congestion and cycle-detour
  penalties;
- zone and connection capacity checks;
- output lines in the subject format;
- output history written to `outputs.txt`;
- terminal-only performance metrics for total turns, average turns per drone,
  and moved drones per turn;
- NiceGUI browser visualization with map selection, playback controls,
  per-drone positions, animated turn movements, live status, and custom SVG;
- unit tests for parser, drone behavior, simulation behavior, capacity
  invariants, visualization adapters, and every supplied benchmark map;
- Makefile targets for installation, execution, debugging, cleanup, linting, and
  tests.

Local verification is complete against the supplied subject 1.6 maps and the
documented Makefile workflow. As with every 42 project, the same commands should
still be rerun on the evaluation machine before the defense.

## Instructions

### Requirements

- Python 3.10 or later
- `pip`
- `flake8`
- `mypy`

Development dependencies are listed in `requirements.txt`.

### Installation

```sh
make install
```

This creates an isolated `.venv` directory and installs the pinned dependency
ranges from `requirements.txt`. Later Makefile commands automatically use that
environment when it exists.

### Run

Run with the default `map.txt`:

```sh
make run
```

Run with another map:

```sh
make run MAP=path/to/map.txt
```

The simulator prints each turn and a final performance summary to the terminal.
Only the movement history is written to `outputs.txt`, keeping the file in the
subject output format.

### Browser Visualizer

Install dependencies once and start the graphical interface:

```sh
make install
make web
```

Open <http://127.0.0.1:8080> if the browser does not open automatically. The
interface provides:

- a selector for `map.txt` and every supplied benchmark map;
- **Load**, **Step**, **Play**, **Pause**, and **Reset** controls;
- turn, moved, waiting, in-transit, active, and delivered counters;
- an SVG network generated from the map coordinates;
- the exact metadata color, type, occupancy, and capacity of every zone;
- labelled connection usage and capacity;
- visible `D<ID>` markers at their current zones or connections;
- quadcopter silhouettes with blinking blue active, cyan moved, rose waiting,
  yellow transit, and green delivered status lights;
- a viewport-sized cockpit that keeps the controls, metrics, latest movement,
  and complete live graph visible together without scrolling on desktop;
- whiteboard navigation with mouse-wheel zoom, click-and-drag pan, `−`/`+`
  controls, and double-click or target-button reset;
- semantic zoom that progressively reveals zone details, connection capacities,
  and drone identifiers instead of overlapping them on dense maps;
- staged origin-to-destination animations with a departure pulse, parallel
  travel lanes, arrival pulse, and final-position reveal;
- explicit two-step feedback for restricted transit and arrival;
- a per-turn explanation and exact location manifest for every drone;
- the subject-format movement line and a scrollable turn history.

An evaluator map outside the supplied collection can be opened directly:

```sh
make web MAP=/path/to/evaluation-map.txt
```

To choose a different port with Make:

```sh
make web PORT=9000
```

To prevent automatic browser opening:

```sh
./.venv/bin/python -m src.web_app --map map.txt --port 9000 --no-open
```

For a deterministic presentation screenshot, start at a specific turn:

```sh
./.venv/bin/python -m src.web_app --map map.txt --turn 1
```

The evaluator-facing CLI remains `make run`. The browser is an additional
presentation mode and does not change terminal output or routing behavior.

### Debug

```sh
make debug MAP=map.txt
```

### Test

```sh
make test
```

### Lint and Type Check

```sh
make lint
```

For stricter mypy checks:

```sh
make lint-strict
```

### Clean

```sh
make clean
```

## Map Format

Example:

```text
nb_drones: 5
start_hub: start 0 0 [color=green]
hub: junction 1 0 [color=yellow max_drones=2]
hub: correct_path 2 0 [color=blue]
end_hub: goal 3 0 [color=green]
connection: start-junction [max_link_capacity=2]
connection: junction-correct_path
connection: correct_path-goal
```

Supported zone declarations:

- `start_hub: <name> <x> <y> [metadata]`
- `end_hub: <name> <x> <y> [metadata]`
- `hub: <name> <x> <y> [metadata]`

Supported connection declaration:

- `connection: <zone1>-<zone2> [metadata]`

Supported zone metadata:

- `zone=normal`
- `zone=blocked`
- `zone=restricted`
- `zone=priority`
- `color=<single_word>`
- `max_drones=<positive_integer>`

Supported connection metadata:

- `max_link_capacity=<positive_integer>`

Zone names must not contain spaces or dashes because dashes are used by the
connection syntax. If `max_drones` is present on `start_hub` or `end_hub`, the
parser accepts it but ignores the value because both endpoints are unlimited in
the current subject.

## Algorithm and Implementation Strategy

The project currently models the map as explicit domain objects:

- `Zone` stores name, coordinates, type, color, capacity, connected edges, and
  current drones.
- `Connection` stores both endpoints, link capacity, and drones currently in
  transit.
- `Graph` owns all instantiated zones and connections.
- `Drone` owns its route state and calculates movement intents.
- `Simulation` coordinates turn execution and resolves conflicts.
- `MapParser` validates input and returns typed intermediate data.

Pathfinding is implemented with Dijkstra's algorithm using only Python standard
library data structures. The destination zone determines movement weight:

- normal zones use weight `1`;
- restricted zones use weight `2`;
- priority zones use weight `0.5` for route preference;
- blocked zones are skipped.

Priority zones still take one real turn to enter. The `0.5` value is only a
pathfinding preference so that equal-looking routes favor priority hubs.

Each turn works in two phases:

1. Active drones propose a `MoveIntent` for their next step.
2. The simulation accepts or rejects intents according to connection and zone
   capacity projections, then commits all accepted movements together.

Departures free zone capacity during the same turn, which allows another drone
to enter a zone as its previous occupant leaves. Restricted-zone movements are
handled as connection transit: the first turn prints the connection name and the
next turn forces arrival at the restricted destination.

The current approach is simple and readable, but it is not yet a complete
long-horizon optimizer. The global scheduler compares all reachable next steps,
projects zone and connection usage, distributes drones across useful parallel
routes, and briefly prefers waiting over a costlier interior detour that would
send a drone around a cycle. Aging the wait score eventually enables a detour
when the shortest corridor remains congested.

Shortest-path results are cached per starting zone. One uncached Dijkstra query
costs `O((V + E) log V)` time. A typical scheduling pass costs
`O(D^2 * degree)` because projected capacity checks inspect the accepted drone
set; retry-heavy turns have a worst case of `O(D^3 * degree)`. Cached routes may
use `O(V^2)` memory in the worst case, while live simulation state uses
`O(V + E + D)`.

## Example Input and Expected Output

Given this map:

```text
nb_drones: 2
start_hub: start 0 0
hub: middle 1 0
end_hub: goal 2 0
connection: start-middle
connection: middle-goal
```

the movement history in `outputs.txt` is:

```text
D1-middle
D1-goal D2-middle
D2-goal
```

The terminal then prints performance metrics separately. Stationary drones are
omitted, which is why `D2` does not appear on the first turn.

## Output Format

Every simulation turn is printed as one line. Each movement uses:

```text
D<ID>-<zone>
```

For a drone entering transit toward a restricted zone, the destination is the
connection name:

```text
D<ID>-<connection>
```

Example:

```text
D1-junction D2-junction
D1-correct_path D3-junction
D1-goal D2-correct_path
```

Drones that do not move during a turn are omitted. Drones that reach the end hub
are considered delivered and are no longer scheduled.

After the movement lines, the terminal displays the total number of turns, the
average delivery turn across all drones, and how many drones moved in each
turn. These metrics are never written to `outputs.txt`.

## Visual Representation

The mandatory visual feedback is provided by the NiceGUI browser page launched
with `make web`. It runs in a normal browser and renders custom SVG from the
integer coordinates in the map. No graph or automatic-layout library is used.
The evaluator-facing algorithm remains available separately through `make run`.

The view makes the simulation state explicit rather than representing drones
only as occupancy totals:

- every zone shows its name, kind, occupancy/capacity, and configured metadata
  color; normal zones are circular, priority zones are hexagonal, restricted
  zones are diamond-shaped, and blocked zones are crossed squares;
- double rings identify the unlimited start/end hubs, while a dashed zone is
  blocked;
- connections show live `usage/capacity` values and expose their full names on
  hover;
- individual quadcopter markers orbit their current zone with their `D<ID>`
  visible underneath; blinking onboard lights communicate active, moved,
  waiting, restricted-transit, and delivered states without a legend;
- each turn separates departure, travel, and arrival into visible phases before
  revealing the drone at its final position; simultaneous drones on the same
  route receive parallel lanes, while restricted transit uses yellow;
- destination pulses, moved/waiting/transit counters, a plain-language turn
  table, a complete drone-position manifest, and raw output history make both
  movement and scheduling decisions inspectable;
- restricted movement is presented as "turn 1 of 2" on the connection and
  "turn 2 of 2" on arrival, matching the subject timing rule.

SVG markers are limited to 16 around one location to keep exceptionally large
fleets readable; any remainder is shown as `+N`. The adjacent manifest still
lists every drone and its exact location, so state is never hidden.

On desktop, the page uses `100dvh` to keep the map controls, live counters,
latest subject-format output, and graphical network inside the first viewport.
The movement explanation, full manifest, visual key, and history remain below
the fold. Narrow screens switch to a scrollable responsive layout so controls
are not compressed into unusable sizes.

The graph behaves like a whiteboard. Scroll over it to zoom around the pointer,
hold the primary mouse button and drag to pan, use `−`/`+` for keyboard-friendly
zoom, and double-click the graph or press the target button to return to the
fitted view. Zoom and pan are stored on the graph container, so stepping or
playing the simulation does not unexpectedly move the camera. Dense maps start
with secondary labels hidden; details appear progressively as the user zooms
in. Above the fitted scale, coordinates spread apart while nodes, drones, and
labels retain a stable on-screen size, so zoom actually resolves collisions
instead of merely enlarging them. Every full value remains available in the
tables and SVG tooltips.

The implementation deliberately keeps the evaluated algorithm independent:

- `src/visualization.py` contains `BrowserSimulation`, the typed adapter around
  `Simulation`, and `SvgMapRenderer`, the dependency-free SVG renderer;
- `src/web_app.py` contains only NiceGUI layout, styling, controls, and server
  startup;
- `src/fly_in.py`, `src/graph.py`, and `src/drone.py` remain the sole owners of
  scheduling, graph logic, pathfinding, and capacity enforcement.

Each browser action calls the same public lifecycle used by the CLI:
`configure()` loads the selected map, and `next_turn()` performs one validated
turn before the view reads the resulting domain state. The visualizer never
calculates a route or approves a movement.

The current web mode is designed for the local, single-evaluator workflow. The
domain registries are process-global, so supporting multiple independent users
on a public deployment would first require making those registries
simulation-scoped.

### Modifying and Improving the Interface

Use these extension points to keep visual changes away from core logic:

- edit `PAGE_STYLES` in `src/web_app.py` for colors, spacing, typography, and
  responsive behavior;
- edit `FlyInWebView._build_controls()` to add controls such as playback speed;
- edit `FlyInWebView._build_status_cards()` to add metrics;
- edit `SvgMapRenderer._zone_markup()` to change zone appearance;
- edit `SvgMapRenderer._connection_markup()` to change connections and transit;
- add values to `SimulationSnapshot` when the UI needs more read-only state.

Good next visual improvements are a speed slider, map upload, mobile-specific
controls, and an end-of-run metrics chart. These should remain presentation-only
and must not introduce a library that performs graph routing or layout.

## Subject 1.6 Compatibility and Benchmarks

Version 1.5 clarified that `max_drones` metadata on the start and end hubs is
accepted but ignored because both endpoints have unlimited occupancy. Version
1.6 additionally requires a paired example input and expected output in this
README. The parser, tests, and documentation cover both changes.

The deterministic test suite currently records these turn counts against the
stricter subject 1.6 targets:

| Map | Result | Target |
| --- | ---: | ---: |
| Linear path | 4 | <= 6 |
| Simple fork | 4 | <= 8 |
| Basic capacity | 4 | <= 6 |
| Dead end trap | 8 | <= 12 |
| Circular loop | 15 | <= 15 |
| Priority puzzle | 7 | <= 12 |
| Maze nightmare | 13 | <= 30 |
| Capacity hell | 18 | <= 35 |
| Ultimate challenge | 26 | <= 45 |
| The Impossible Dream (optional) | 44 | < 45 |

Run `make test` to execute these benchmark checks together with per-turn zone,
connection, and restricted-transit invariants.

## Resources

Classic references used or useful for this project:

- Python documentation: `heapq`
  <https://docs.python.org/3/library/heapq.html>
- Python documentation: `dataclasses`
  <https://docs.python.org/3/library/dataclasses.html>
- Python documentation: `typing`
  <https://docs.python.org/3/library/typing.html>
- Python documentation: `unittest`
  <https://docs.python.org/3/library/unittest.html>
- Flake8 documentation
  <https://flake8.pycqa.org/>
- Mypy documentation
  <https://mypy.readthedocs.io/>
- NiceGUI documentation
  <https://nicegui.io/documentation>
- Dijkstra's shortest path algorithm overview
  <https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm>

AI usage:

- AI was used as a development assistant to organize implementation steps,
  review requirements from the subject, draft tests, build the browser
  presentation adapter, and improve documentation.
- AI-generated suggestions were checked against the subject requirements and the
  local test suite before being kept.
