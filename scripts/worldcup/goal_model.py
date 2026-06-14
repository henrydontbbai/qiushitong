from __future__ import annotations

import math
from typing import List, Tuple

from .elo import clamp


BASE_EACH_GOAL = 1.225
GOAL_SCALE = 240.0
MAX_ADJUSTMENT = 0.85
MIN_XG = 0.35
MAX_XG = 3.20


def estimate_expected_goals(home_elo: float, away_elo: float, neutral_site: bool = True, home_advantage: float = 0.0) -> tuple[float, float]:
    elo_diff = (home_elo - away_elo) + (0.0 if neutral_site else home_advantage)
    adjustment = clamp(elo_diff / GOAL_SCALE, -MAX_ADJUSTMENT, MAX_ADJUSTMENT)
    home_xg = clamp(BASE_EACH_GOAL + adjustment, MIN_XG, MAX_XG)
    away_xg = clamp(BASE_EACH_GOAL - adjustment, MIN_XG, MAX_XG)
    return round(home_xg, 4), round(away_xg, 4)


def poisson_probability(lam: float, goals: int) -> float:
    return math.exp(-lam) * (lam ** goals) / math.factorial(goals)


def probability_grid(home_xg: float, away_xg: float, max_goals: int = 7) -> List[Tuple[int, int, float]]:
    grid = []
    for home_goals in range(0, max_goals + 1):
        for away_goals in range(0, max_goals + 1):
            prob = poisson_probability(home_xg, home_goals) * poisson_probability(away_xg, away_goals)
            grid.append((home_goals, away_goals, prob))
    total = sum(prob for _, _, prob in grid) or 1.0
    return [(h, a, prob / total) for h, a, prob in grid]


def result_probabilities(home_xg: float, away_xg: float) -> dict:
    grid = probability_grid(home_xg, away_xg)
    home_win = sum(prob for home, away, prob in grid if home > away)
    draw = sum(prob for home, away, prob in grid if home == away)
    away_win = sum(prob for home, away, prob in grid if home < away)
    total = home_win + draw + away_win or 1.0
    return {
        'home_win': round(home_win / total, 6),
        'draw': round(draw / total, 6),
        'away_win': round(away_win / total, 6),
    }


def top_scorelines(home_xg: float, away_xg: float, top_n: int = 5) -> List[dict]:
    grid = probability_grid(home_xg, away_xg)
    ranked = sorted(grid, key=lambda item: item[2], reverse=True)[:top_n]
    return [
        {'home_goals': home, 'away_goals': away, 'probability': round(prob, 6)}
        for home, away, prob in ranked
    ]
