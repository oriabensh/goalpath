import math
import random

from app.geo import destination_point


def generate_goal_candidate(
    lat: float, lon: float, min_m: float, max_m: float, rng: random.Random | None = None
) -> tuple[float, float]:
    """Random point uniform by area in the ring [min_m, max_m] around (lat, lon).

    Snapping to the walkable network and the reachability check are added in step 2.
    """
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"invalid coordinates: ({lat}, {lon})")
    if not (math.isfinite(min_m) and math.isfinite(max_m)) or min_m < 0 or min_m >= max_m:
        raise ValueError(f"invalid distance range: min={min_m}, max={max_m}")

    rng = rng or random.Random()
    # sqrt keeps the density uniform per area, so points don't cluster near the player
    distance = math.sqrt(rng.random() * (max_m**2 - min_m**2) + min_m**2)
    bearing = rng.uniform(0, 360)
    return destination_point(lat, lon, bearing, distance)
