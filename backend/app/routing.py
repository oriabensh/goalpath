import heapq
import itertools
import math

import networkx as nx

from app.geo import haversine_m


class NoPathError(Exception):
    """No walkable path between the two nodes."""


def _coords(G: nx.Graph, node) -> tuple[float, float]:
    d = G.nodes[node]
    return d["y"], d["x"]


def nearest_node(G: nx.Graph, lat: float, lon: float):
    # O(n) scan; a spatial index (KD-tree / R-tree) is the scaling path.
    return min(G.nodes, key=lambda n: haversine_m(lat, lon, *_coords(G, n)))


def _best_edge(G: nx.Graph, u, v) -> dict:
    """Edge data for u->v; the shortest one if there are parallel edges."""
    data = G.adj[u][v]
    return min(data.values(), key=lambda d: d["length"]) if G.is_multigraph() else data


def astar(G: nx.Graph, source, target) -> tuple[list, float]:
    """Shortest path by edge 'length' (meters). Haversine to target is admissible, so the result is optimal."""
    for node in (source, target):
        if node not in G:
            raise ValueError(f"node {node!r} is not in the graph")

    target_lat, target_lon = _coords(G, target)

    def h(node) -> float:
        return haversine_m(*_coords(G, node), target_lat, target_lon)

    g = {source: 0.0}
    came_from = {}
    closed = set()
    tie = itertools.count()  # avoids comparing node ids on equal f
    open_heap = [(h(source), next(tie), source)]

    while open_heap:
        _, _, node = heapq.heappop(open_heap)
        if node == target:
            path = [node]
            while node in came_from:
                node = came_from[node]
                path.append(node)
            return path[::-1], g[target]
        if node in closed:
            continue
        closed.add(node)
        for nbr in G.adj[node]:
            if nbr in closed:
                continue
            cost = g[node] + _best_edge(G, node, nbr)["length"]
            if cost < g.get(nbr, math.inf):
                g[nbr] = cost
                came_from[nbr] = node
                heapq.heappush(open_heap, (cost + h(nbr), next(tie), nbr))

    raise NoPathError(f"no path from {source!r} to {target!r}")


def route_coords(G: nx.Graph, node_list: list) -> list[tuple[float, float]]:
    """(lat, lon) points along the path, following street geometry where available."""
    if not node_list:
        return []
    points = [_coords(G, node_list[0])]
    for u, v in zip(node_list, node_list[1:]):
        geom = _best_edge(G, u, v).get("geometry")
        if geom is None:
            points.append(_coords(G, v))
            continue
        seg = [(y, x) for x, y in geom.coords]
        # Geometry may be stored v->u on reverse edges; orient it from u.
        if haversine_m(*seg[0], *points[-1]) > haversine_m(*seg[-1], *points[-1]):
            seg.reverse()
        points.extend(seg[1:])
    return points
