import math

EARTH_RADIUS_M = 6_371_008.8  # mean Earth radius


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, a)))


def destination_point(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    """Point reached from (lat, lon) after distance_m along bearing_deg (0 = north)."""
    p1, l1 = math.radians(lat), math.radians(lon)
    theta = math.radians(bearing_deg)
    delta = distance_m / EARTH_RADIUS_M
    p2 = math.asin(math.sin(p1) * math.cos(delta) + math.cos(p1) * math.sin(delta) * math.cos(theta))
    l2 = l1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(p1),
        math.cos(delta) - math.sin(p1) * math.sin(p2),
    )
    lon2 = (math.degrees(l2) + 540) % 360 - 180  # normalize to [-180, 180)
    return math.degrees(p2), lon2


def point_segment_distance_m(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    """Distance in meters from point p to segment a-b (lat, lon). Local flat projection; fine at street scale."""
    k = math.cos(math.radians(p[0]))  # meters per degree of lon / meters per degree of lat

    def xy(q: tuple[float, float]) -> tuple[float, float]:
        return (q[1] - p[1]) * k, q[0] - p[0]

    (ax, ay), (bx, by) = xy(a), xy(b)
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    t = 0.0 if seg2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / seg2))
    cx, cy = ax + t * dx, ay + t * dy  # closest point, relative to p
    return math.radians(math.hypot(cx, cy)) * EARTH_RADIUS_M
