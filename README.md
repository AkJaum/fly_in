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
- zone and connection capacity checks;
- output lines in the subject format;
- output history written to `outputs.txt`;
- terminal-only performance metrics for total turns, average turns per drone,
  and moved drones per turn;
- unit tests for parser, drone behavior, and simulation behavior;
- Makefile targets for installation, execution, debugging, cleanup, linting, and
  tests.

Still needs improvement before final evaluation:

- add colored terminal output or a graphical view to fully satisfy the visual
  representation requirement;
- improve path distribution across multiple available routes instead of relying
  mainly on each drone's local shortest route;
- add stronger deadlock-prevention and recovery strategies for complex maps;
- benchmark easy, medium, hard, and challenger maps against the subject targets;
- expand tests with larger maps, overlapping routes, and difficult capacity
  scenarios;
- run and keep the project clean under the exact peer-evaluation environment.

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
global optimizer. It recalculates a shortest remaining route when a drone does
not already have one, and it does not yet perform advanced multi-path balancing
or long-horizon scheduling.

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

The project currently provides a textual turn-by-turn representation in the
terminal and mirrors it to `outputs.txt`. This already helps peer reviewers
trace which drone moved at each turn and verify the subject output format.

The next required improvement is a richer visual representation. The planned
minimum is colored terminal output based on the optional `color=<value>`
metadata, with clear feedback for normal hubs, priority hubs, restricted hubs,
blocked hubs, and delivered drones. A later improvement could add a graphical
view of the graph and live drone positions.

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
- Dijkstra's shortest path algorithm overview
  <https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm>

AI usage:

- AI was used as a development assistant to organize implementation steps,
  review requirements from the subject, draft tests, and improve documentation.
- AI-generated suggestions were checked against the subject requirements and the
  local test suite before being kept.
