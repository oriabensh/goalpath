import networkx as nx
import pytest

from app.geo import destination_point
from app.routing import NoPathError, astar

S, A, B, T, X, ISLAND = range(6)


def _graph() -> nx.MultiDiGraph:
    # S -> A -> B -> T runs straight north (3 hops, 330 m).
    # S -> X -> T detours 400 m east (2 hops, 900 m). ISLAND has no edges.
    base = (32.08, 34.78)
    coords = {
        S: base,
        A: destination_point(*base, 0, 100),
        B: destination_point(*base, 0, 200),
        T: destination_point(*base, 0, 300),
        X: destination_point(*destination_point(*base, 0, 150), 90, 400),
        ISLAND: destination_point(*base, 180, 500),
    }
    G = nx.MultiDiGraph()
    for node, (lat, lon) in coords.items():
        G.add_node(node, y=lat, x=lon)
    for u, v, length in [(S, A, 110), (A, B, 110), (B, T, 110), (S, X, 450), (X, T, 450)]:
        G.add_edge(u, v, length=length)
        G.add_edge(v, u, length=length)
    return G


def test_astar_prefers_shortest_distance_over_fewest_hops():
    path, length = astar(_graph(), S, T)
    assert path == [S, A, B, T]
    assert length == pytest.approx(330)


def test_astar_unreachable_goal_raises():
    with pytest.raises(NoPathError):
        astar(_graph(), S, ISLAND)


def test_astar_unknown_node_raises():
    with pytest.raises(ValueError):
        astar(_graph(), S, 999)
