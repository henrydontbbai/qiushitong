from __future__ import annotations


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def calculate_elo_adjustment(home_elo: float, away_elo: float, neutral_site: bool = True, home_advantage: float = 0.0) -> float:
    advantage = 0.0 if neutral_site else home_advantage
    return (home_elo - away_elo) + advantage
