"""Domain objects for a Fly-in map."""

from typing import TYPE_CHECKING

from src.parser import ConnectionData, HubData

if TYPE_CHECKING:
    from src.drone import Drone


class Zone:
    """Represent a zone in the Fly-in map."""

    _all_zones: list["Zone"] = []

    def __init__(self, hub_config: HubData) -> None:
        """Create a zone from validated parser data."""
        self.name: str = hub_config["name"]
        self.kind: str = hub_config["kind"]
        self.pos: tuple[int, int] = (hub_config["x"], hub_config["y"])
        self.connections: list["Connection"] = []
        self.is_start: bool = hub_config.get("is_start", False)
        self.is_end: bool = hub_config.get("is_end", False)
        self.max_drones: int = hub_config.get("max_drones", 1)
        self.color: str | None = hub_config.get("color", None)
        self.weight: float = self._calculate_weight()
        self.drones_in: list["Drone"] = []

        Zone._all_zones.append(self)

    def _calculate_weight(self) -> float:
        """Calculate weight based on zone kind."""
        if self.kind == "normal":
            return 1.0
        elif self.kind == "restricted":
            return 2.0
        elif self.kind == "priority":
            return 0.5
        else:
            return float("inf")

    def __repr__(self) -> str:
        """Return a string representation of the Zone object."""
        return f"Zone(name={self.name}, kind={self.kind}, pos={self.pos})"

    @classmethod
    def reset(cls) -> None:
        """Clear all zones. Useful for testing."""
        cls._all_zones.clear()


class Connection:
    """Represent an undirected connection between two zones."""

    _all_connections: list["Connection"] = []

    def __init__(
        self,
        connection_config: ConnectionData,
        from_zone: Zone,
        to_zone: Zone,
    ) -> None:
        """Create a connection from validated parser data."""
        self.name = f"{from_zone.name}-{to_zone.name}"
        self.previous_zone: Zone = from_zone
        self.next_zone: Zone = to_zone
        self.max_link_capacity = connection_config["max_link_capacity"]
        self.drones_in: list["Drone"] = []

        # Register connection in zones
        from_zone.connections.append(self)
        to_zone.connections.append(self)
        Connection._all_connections.append(self)

    def __repr__(self) -> str:
        """Return a string representation of the connection."""
        return (
            f"Connection({self.previous_zone.name}-{self.next_zone.name}, "
            f"capacity={self.max_link_capacity})"
        )

    def other_zone(self, current_zone: Zone) -> Zone:
        """Return the endpoint opposite ``current_zone``."""
        if current_zone is self.previous_zone:
            return self.next_zone
        if current_zone is self.next_zone:
            return self.previous_zone
        raise ValueError(
            f"Zone '{current_zone.name}' does not belong to {self.name}"
        )

    @classmethod
    def reset(cls) -> None:
        """Clear all connections. Useful for testing."""
        cls._all_connections.clear()
