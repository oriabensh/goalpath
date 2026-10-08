import math
import random
import time

import networkx as nx

from app.geo import haversine_m
from app.goal import place_goal
from app.routing import astar, nearest_node, route_coords

MIN_STEP_M = 5.0  # smallest movement counted toward distance walked


def _check_position(lat: float, lon: float) -> None:
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"invalid coordinates: ({lat}, {lon})")


class GameSession:
    """One player's game: goal, route, and progress. Transport-agnostic."""

    def __init__(
        self,
        G: nx.Graph,
        lat: float,
        lon: float,
        *,
        min_m: float,
        max_m: float,
        threshold_m: float,
        max_attempts: int = 20,
        rng: random.Random | None = None,
    ):
        _check_position(lat, lon)
        self.threshold_m = threshold_m
        self.goal_node = place_goal(G, lat, lon, min_m, max_m, rng, max_attempts)
        self.goal = (G.nodes[self.goal_node]["y"], G.nodes[self.goal_node]["x"])
        path, street_length_m = astar(G, nearest_node(G, lat, lon), self.goal_node)
        street = route_coords(G, path)
        # Start at the player's real position; first segment connects to the street.
        self.route = [(lat, lon)] + street
        self.route_length_m = haversine_m(lat, lon, *street[0]) + street_length_m
        self.player = (lat, lon)
        self._walk_anchor = (lat, lon)  # last position counted toward distance walked
        self.started_at = time.monotonic()
        self.finished_at: float | None = None
        self.distance_walked_m = 0.0
        self.accuracy_m: float | None = None

    @property
    def finished(self) -> bool:
        return self.finished_at is not None

    def _state(self, just_reached: bool) -> dict:
        end = self.finished_at if self.finished else time.monotonic()
        return {
            "player": {"lat": self.player[0], "lon": self.player[1]},
            "accuracy_m": self.accuracy_m,
            "distance_to_goal_m": haversine_m(*self.player, *self.goal),
            "reached": self.finished,
            "just_reached": just_reached,
            "elapsed_s": end - self.started_at,
            "distance_walked_m": self.distance_walked_m,
        }

    def update_position(self, lat: float, lon: float, accuracy_m: float | None = None) -> dict:
        """Apply a position fix. Accuracy is display-only; it never blocks goal detection."""
        _check_position(lat, lon)
        if self.finished:
            return self._state(just_reached=False)  # final state, frozen

        # Count a step only beyond max(5 m, accuracy), measured from the last counted point,
        # so GPS jitter is ignored but slow walking still accumulates.
        step = haversine_m(*self._walk_anchor, lat, lon)
        if step > max(MIN_STEP_M, accuracy_m or 0):
            self.distance_walked_m += step
            self._walk_anchor = (lat, lon)
        self.player = (lat, lon)
        self.accuracy_m = accuracy_m
        if haversine_m(lat, lon, *self.goal) <= self.threshold_m:
            self.finished_at = time.monotonic()
            return self._state(just_reached=True)
        return self._state(just_reached=False)
