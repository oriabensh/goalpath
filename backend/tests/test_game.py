import random

import networkx as nx
import pytest

from app.geo import destination_point
from app.game import GameSession

PLAYER = (32.08, 34.78)
THRESHOLD_M = 20


def _session() -> GameSession:
    # Player node plus a ring of 8 nodes 300 m away, each linked to the player.
    G = nx.MultiDiGraph()
    G.add_node("p", y=PLAYER[0], x=PLAYER[1])
    for i in range(8):
        lat, lon = destination_point(*PLAYER, i * 45, 300)
        G.add_node(i, y=lat, x=lon)
        G.add_edge("p", i, length=320)
        G.add_edge(i, "p", length=320)
    return GameSession(
        G, *PLAYER, min_m=100, max_m=500, threshold_m=THRESHOLD_M, rng=random.Random(0)
    )


def test_goal_reached_within_threshold():
    session = _session()
    state = session.update_position(*destination_point(*session.goal, 90, 5))
    assert state["reached"] is True


def test_not_reached_just_outside_threshold():
    session = _session()
    state = session.update_position(*destination_point(*session.goal, 90, THRESHOLD_M + 2))
    assert state["reached"] is False


def test_invalid_position_raises():
    with pytest.raises(ValueError):
        _session().update_position(91, 34.78)
