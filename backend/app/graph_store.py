from functools import lru_cache
from pathlib import Path

import networkx as nx
import osmnx as ox

from app.geo import destination_point

GRAPH_PATH = Path(__file__).resolve().parents[1] / "data" / "tel_aviv_walk.graphml"


class OutsideCoverageError(Exception):
    """The player (plus the goal radius) is outside the bundled map area."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code  # "outside_coverage" or "near_edge"
        self.message = message


@lru_cache
def get_graph() -> nx.MultiDiGraph:
    # Loaded once per process and kept in memory.
    return ox.load_graphml(GRAPH_PATH)


@lru_cache
def get_bounds() -> tuple[float, float, float, float]:
    """(min_lat, min_lon, max_lat, max_lon) of the graph's nodes."""
    nodes = get_graph().nodes
    lats = [d["y"] for _, d in nodes(data=True)]
    lons = [d["x"] for _, d in nodes(data=True)]
    return min(lats), min(lons), max(lats), max(lons)


def is_covered(lat: float, lon: float, radius_m: float) -> bool:
    """True if the circle of radius_m around (lat, lon) fits inside the graph bounds."""
    min_lat, min_lon, max_lat, max_lon = get_bounds()
    north, _ = destination_point(lat, lon, 0, radius_m)
    south, _ = destination_point(lat, lon, 180, radius_m)
    _, east = destination_point(lat, lon, 90, radius_m)
    _, west = destination_point(lat, lon, 270, radius_m)
    return min_lat <= south and north <= max_lat and min_lon <= west and east <= max_lon


def ensure_covered(lat: float, lon: float, radius_m: float) -> None:
    if is_covered(lat, lon, radius_m):
        return
    min_lat, min_lon, max_lat, max_lon = get_bounds()
    if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
        raise OutsideCoverageError(
            "near_edge",
            f"Too close to the edge of the covered area (central Tel Aviv): the goal radius "
            f"({radius_m:.0f} m) must fit inside the map.",
        )
    raise OutsideCoverageError(
        "outside_coverage",
        f"Position ({lat:.5f}, {lon:.5f}) is outside the covered area "
        f"(central Tel Aviv-Yafo: lat {min_lat:.4f}..{max_lat:.4f}, lon {min_lon:.4f}..{max_lon:.4f}).",
    )
