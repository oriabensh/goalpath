import math
import random

import networkx as nx

from app.geo import destination_point, haversine_m
from app.routing import NoPathError, astar, nearest_node


class GoalPlacementError(Exception):
    """No valid goal found within the retry limit."""


def generate_goal_candidate(
    lat: float, lon: float, min_m: float, max_m: float, rng: random.Random | None = None
) -> tuple[float, float]:
    """Random point uniform by area in the ring [min_m, max_m] around (lat, lon). Not snapped; see place_goal."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"invalid coordinates: ({lat}, {lon})")
    if not (math.isfinite(min_m) and math.isfinite(max_m)) or min_m < 0 or min_m >= max_m:
        raise ValueError(f"invalid distance range: min={min_m}, max={max_m}")

    rng = rng or random.Random()
    # sqrt keeps the density uniform per area, so points don't cluster near the player
    distance = math.sqrt(rng.random() * (max_m**2 - min_m**2) + min_m**2)
    bearing = rng.uniform(0, 360)
    return destination_point(lat, lon, bearing, distance)


def place_goal(
    G: nx.Graph,
    player_lat: float,
    player_lon: float,
    min_m: float,
    max_m: float,
    rng: random.Random | None = None,
    max_attempts: int = 20,
):
    """Goal node: a candidate snapped to its nearest node, kept only if still in [min_m, max_m] and reachable."""
    rng = rng or random.Random()
    start = nearest_node(G, player_lat, player_lon)
    for _ in range(max_attempts):
        lat, lon = generate_goal_candidate(player_lat, player_lon, min_m, max_m, rng)
        node = nearest_node(G, lat, lon)
        node_lat, node_lon = G.nodes[node]["y"], G.nodes[node]["x"]
        if not min_m <= haversine_m(player_lat, player_lon, node_lat, node_lon) <= max_m:
            continue
        try:
            astar(G, start, node)
        except NoPathError:
            continue
        return node
    raise GoalPlacementError(
        f"no reachable goal {min_m:.0f}-{max_m:.0f} m from ({player_lat:.5f}, {player_lon:.5f}) "
        f"after {max_attempts} attempts"
    )
