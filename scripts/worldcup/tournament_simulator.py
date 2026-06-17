from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, Iterable, List

from .bracket_rules import build_round_of_32, load_bracket_rules, validate_bracket_rules
from .data_loader import WorldCupData
from .goal_model import estimate_expected_goals, probability_grid
from .group_simulator import _simulate_once
from .standings import team_public_name


ROUND_OF_16_PATH = [
    ("M89", "M74", "M77"),
    ("M90", "M73", "M75"),
    ("M91", "M76", "M78"),
    ("M92", "M79", "M80"),
    ("M93", "M83", "M84"),
    ("M94", "M81", "M82"),
    ("M95", "M86", "M88"),
    ("M96", "M85", "M87"),
]

QUARTER_FINAL_PATH = [
    ("M97", "M89", "M90"),
    ("M98", "M93", "M94"),
    ("M99", "M91", "M92"),
    ("M100", "M95", "M96"),
]

SEMI_FINAL_PATH = [
    ("M101", "M97", "M98"),
    ("M102", "M99", "M100"),
]

FINAL_PATH = [("M104", "M101", "M102")]

ROUND_KEYS = [
    "round_of_32_probability",
    "round_of_16_probability",
    "quarter_final_probability",
    "semi_final_probability",
    "final_probability",
    "champion_probability",
]


def simulate_tournament(
    data: WorldCupData,
    data_dir: str | Path,
    trials: int = 1000,
    seed: int | None = 2026,
) -> dict:
    """Simulate the 2026 World Cup path from group stage to champion.

    AI, database data, and market odds are intentionally not used here. The
    knockout stage allows a 90-minute draw in the score sampler, but every
    knockout match is resolved to one advancing team with an Elo-based
    extra-time/penalty simplification.
    """
    trials = _safe_trials(trials)
    rng = random.Random(seed)
    rules = load_bracket_rules(data_dir)
    rules_summary = validate_bracket_rules(rules)
    team_index = _team_index(data)
    counters = {team_id: {key: 0 for key in ROUND_KEYS} for team_id in team_index}

    for _ in range(trials):
        simulated_standings = {"success": True, "groups": _simulate_once(data, rng)}
        bracket = build_round_of_32(
            simulated_standings,
            data_dir,
            rules=rules,
            rules_summary=rules_summary,
            validate_rules=False,
        )

        winners: Dict[str, dict] = {}
        for match in bracket["matches"]:
            team_a = match["team_a"]
            team_b = match["team_b"]
            _increment(counters, [team_a, team_b], "round_of_32_probability")
            winner = _simulate_knockout_match(data, team_a, team_b, rng)
            winners[str(match["match_id"])] = winner
            _increment(counters, [winner], "round_of_16_probability")

        _simulate_round(data, ROUND_OF_16_PATH, winners, counters, "quarter_final_probability", rng)
        _simulate_round(data, QUARTER_FINAL_PATH, winners, counters, "semi_final_probability", rng)
        _simulate_round(data, SEMI_FINAL_PATH, winners, counters, "final_probability", rng)
        _simulate_round(data, FINAL_PATH, winners, counters, "champion_probability", rng)

    teams = []
    for team_id, team in team_index.items():
        row = {
            "team_id": team_id,
            "team_name": team_public_name(team),
            "group": str(team.get("group") or "").upper(),
        }
        for key in ROUND_KEYS:
            row[key] = round(counters[team_id][key] / trials, 6)
        teams.append(row)

    teams.sort(
        key=lambda row: (
            -row["champion_probability"],
            -row["final_probability"],
            -row["semi_final_probability"],
            -row["quarter_final_probability"],
            -row["round_of_16_probability"],
            row["team_id"],
        )
    )

    round_totals = {
        key: sum(counters[team_id][key] for team_id in counters) / trials
        for key in ROUND_KEYS
    }

    return {
        "success": True,
        "trials": trials,
        "seed": seed,
        "teams": teams,
        "round_totals": round_totals,
        "model_version": data.model_version,
        "data_cutoff_at": data.data_cutoff_at,
        "base_data_cutoff_at": data.base_data_cutoff_at,
        "effective_data_cutoff_at": data.data_cutoff_at,
        "local_patch_applied": data.local_patch_applied,
        "local_patch_matches_count": data.local_patch_matches_count,
        "update_source_mode": data.update_source_mode,
        "disclaimer": "冠军路径模拟为概率参考，不代表赛果保证；AI 不参与概率计算。",
        "notes": [
            "小组赛使用 Monte Carlo 模拟，已完赛比分会锁定。",
            "淘汰赛 90 分钟允许平局，但晋级方会用 Elo 简化模型决出。",
        ],
    }


def _simulate_round(
    data: WorldCupData,
    path: Iterable[tuple[str, str, str]],
    winners: Dict[str, dict],
    counters: Dict[str, dict],
    next_round_key: str,
    rng: random.Random,
) -> None:
    for match_id, left_ref, right_ref in path:
        winner = _simulate_knockout_match(data, winners[left_ref], winners[right_ref], rng)
        winners[match_id] = winner
        _increment(counters, [winner], next_round_key)


def _simulate_knockout_match(data: WorldCupData, team_a: dict, team_b: dict, rng: random.Random) -> dict:
    team_a_elo = _team_elo(data, team_a.get("team_id"))
    team_b_elo = _team_elo(data, team_b.get("team_id"))
    team_a_xg, team_b_xg = estimate_expected_goals(team_a_elo, team_b_elo, neutral_site=True)
    team_a_goals, team_b_goals = _sample_score(team_a_xg, team_b_xg, rng)
    if team_a_goals > team_b_goals:
        return team_a
    if team_b_goals > team_a_goals:
        return team_b
    return team_a if rng.random() <= _elo_advancement_probability(team_a_elo, team_b_elo) else team_b


def _sample_score(home_xg: float, away_xg: float, rng: random.Random) -> tuple[int, int]:
    draw = rng.random()
    cumulative = 0.0
    for home_goals, away_goals, probability in probability_grid(home_xg, away_xg):
        cumulative += probability
        if draw <= cumulative:
            return home_goals, away_goals
    return 0, 0


def _elo_advancement_probability(team_a_elo: float, team_b_elo: float) -> float:
    return 1 / (1 + 10 ** (-(team_a_elo - team_b_elo) / 400))


def _team_elo(data: WorldCupData, team_id: object) -> float:
    rating = data.ratings.get(str(team_id), {})
    return float(rating.get("elo") or 1800)


def _team_index(data: WorldCupData) -> Dict[str, dict]:
    return {str(team.get("team_id")): team for team in data.teams if team.get("team_id")}


def _increment(counters: Dict[str, dict], teams: Iterable[dict], key: str) -> None:
    for team in teams:
        team_id = str(team.get("team_id") or "")
        if team_id in counters:
            counters[team_id][key] += 1


def _safe_trials(trials: int) -> int:
    try:
        value = int(trials)
    except (TypeError, ValueError):
        value = 1000
    return max(1, min(value, 5000))
