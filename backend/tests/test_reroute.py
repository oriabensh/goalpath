import random

import networkx as nx
import pytest

from app.geo import destination_point
from app.game import GameSession

PLAYER = (32.08, 34.78)


def _session() -> GameSession:
    # Player node plus a ring of 8 nodes 300 m away (node i at bearing i * 45), each linked to the player.
    G = nx.MultiDiGraph()
    G.add_node("p", y=PLAYER[0], x=PLAYER[1])
    for i in range(8):
        lat, lon = destination_point(*PLAYER, i * 45, 300)
        G.add_node(i, y=lat, x=lon)
        G.add_edge("p", i, length=320)
        G.add_edge(i, "p", length=320)
    return GameSession(
        G, *PLAYER, min_m=100, max_m=500, threshold_m=20, reroute_threshold_m=25, rng=random.Random(0)
    )


def test_reroute_when_player_deviates():
    session = _session()
    bearing = session.goal_node * 45
    off_route = destination_point(*destination_point(*PLAYER, bearing, 150), bearing + 90, 150)

    state = session.update_position(*off_route)

    assert state["rerouted"] is True
    assert state["route"][0] == off_route
    assert state["route"][-1] == pytest.approx(session.goal)


def test_no_reroute_for_small_jitter():
    session = _session()
    bearing = session.goal_node * 45
    jitter = destination_point(*destination_point(*PLAYER, bearing, 150), bearing + 90, 5)

    state = session.update_position(*jitter)

    assert state["rerouted"] is False
    assert state["route"][-1] == pytest.approx(session.goal)


def test_position_outside_graph_keeps_last_route():
    session = _session()
    route_before = list(session.route)

    state = session.update_position(31.0, 35.0)

    assert state["off_coverage"] is True
    assert state["route"] == route_before
