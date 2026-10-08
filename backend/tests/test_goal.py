import random

import pytest

from app.geo import haversine_m
from app.goal import generate_goal_candidate

PLAYER = (32.0853, 34.7818)  # Tel Aviv


def test_goal_within_radius_and_min_distance():
    rng = random.Random(42)
    for _ in range(200):
        goal = generate_goal_candidate(*PLAYER, 100, 500, rng=rng)
        assert 100 - 1 <= haversine_m(*PLAYER, *goal) <= 500 + 1


def test_goal_in_narrow_ring():
    rng = random.Random(7)
    for _ in range(50):
        goal = generate_goal_candidate(*PLAYER, 499, 500, rng=rng)
        assert 499 - 1 <= haversine_m(*PLAYER, *goal) <= 500 + 1


def test_invalid_input_raises():
    with pytest.raises(ValueError):
        generate_goal_candidate(91, 34.78, 100, 500)
    with pytest.raises(ValueError):
        generate_goal_candidate(*PLAYER, 500, 500)
