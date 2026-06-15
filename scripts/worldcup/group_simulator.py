from __future__ import annotations

from copy import deepcopy
import random
from typing import Dict, List

from .data_loader import WorldCupData
from .goal_model import estimate_expected_goals, probability_grid
from .standings import best_third_rows, rank_group_rows, team_public_name


def simulate_group_stage(data: WorldCupData, trials: int = 2000, seed: int | None = None) -> dict:
    """Monte Carlo group-stage simulation for the 2026 format.

    Scope is intentionally limited to groups:
    - 12 groups of 4 teams.
    - Top 2 in every group qualify.
    - Best 8 third-place teams qualify.
    """
    trials = _safe_trials(trials)
    rng = random.Random(seed)
    teams = _team_map(data)
    counters = {
        team_id: {
            "group_first": 0,
            "top_two": 0,
            "third_qualify": 0,
            "qualify": 0,
        }
        for team_id in teams
    }

    for _ in range(trials):
        simulated_groups = _simulate_once(data, rng)
        third_ranked = best_third_rows(simulated_groups)
        third_qualifiers = {row["team_id"] for row in third_ranked[:8]}

        for group in simulated_groups:
            ranked = group["teams"]
            if not ranked:
                continue
            counters[ranked[0]["team_id"]]["group_first"] += 1
            for row in ranked[:2]:
                counters[row["team_id"]]["top_two"] += 1
                counters[row["team_id"]]["qualify"] += 1
            if len(ranked) >= 3 and ranked[2]["team_id"] in third_qualifiers:
                counters[ranked[2]["team_id"]]["third_qualify"] += 1
                counters[ranked[2]["team_id"]]["qualify"] += 1

    groups_payload = []
    for group_name in sorted({str(team.get("group") or "").upper() for team in data.teams}):
        group_teams = []
        for team in data.teams:
            if str(team.get("group") or "").upper() != group_name:
                continue
            team_id = str(team.get("team_id"))
            counts = counters[team_id]
            group_teams.append(
                {
                    "team_id": team_id,
                    "team_name": team_public_name(team),
                    "group_first_probability": counts["group_first"] / trials,
                    "top_two_probability": counts["top_two"] / trials,
                    "third_qualify_probability": counts["third_qualify"] / trials,
                    "qualify_probability": counts["qualify"] / trials,
                }
            )
        group_teams.sort(key=lambda row: (-row["qualify_probability"], -row["group_first_probability"], row["team_id"]))
        groups_payload.append({"group": group_name, "teams": group_teams})

    return {
        "success": True,
        "trials": trials,
        "seed": seed,
        "groups": groups_payload,
        "rules": "2026 赛制：12 个小组，每组前 2 名晋级，另取 8 个成绩最好的小组第三。",
        "model_version": data.model_version,
        "data_cutoff_at": data.data_cutoff_at,
        "disclaimer": "小组出线概率为模拟结果，概率不代表赛果保证。",
    }


def _simulate_once(data: WorldCupData, rng: random.Random) -> List[dict]:
    group_rows = _initial_rows(data)
    for fixture in data.fixtures:
        if fixture.get("stage") != "group":
            continue
        group_name = str(fixture.get("group") or "").upper()
        home_id = str(fixture.get("home_team_id") or "")
        away_id = str(fixture.get("away_team_id") or "")
        if group_name not in group_rows or home_id not in group_rows[group_name] or away_id not in group_rows[group_name]:
            continue
        home_goals, away_goals = _fixture_score(data, fixture, rng)
        _apply_score(group_rows[group_name][home_id], home_goals, away_goals)
        _apply_score(group_rows[group_name][away_id], away_goals, home_goals)

    groups = []
    for group_name in sorted(group_rows.keys()):
        ranked = rank_group_rows(group_rows[group_name].values())
        for index, row in enumerate(ranked, start=1):
            row["rank"] = index
        groups.append({"group": group_name, "teams": ranked})
    return groups


def _fixture_score(data: WorldCupData, fixture: dict, rng: random.Random) -> tuple[int, int]:
    if str(fixture.get("status") or "").lower() == "finished" and fixture.get("final_score"):
        score = fixture["final_score"]
        return int(score.get("home", 0)), int(score.get("away", 0))

    home_id = str(fixture.get("home_team_id") or "")
    away_id = str(fixture.get("away_team_id") or "")
    home_rating = data.ratings.get(home_id, {})
    away_rating = data.ratings.get(away_id, {})
    home_elo = float(home_rating.get("elo") or 1800)
    away_elo = float(away_rating.get("elo") or 1800)
    home_xg, away_xg = estimate_expected_goals(
        home_elo,
        away_elo,
        neutral_site=bool(fixture.get("neutral_site", True)),
    )
    return _sample_score(home_xg, away_xg, rng)


def _sample_score(home_xg: float, away_xg: float, rng: random.Random) -> tuple[int, int]:
    draw = rng.random()
    cumulative = 0.0
    for home_goals, away_goals, probability in probability_grid(home_xg, away_xg):
        cumulative += probability
        if draw <= cumulative:
            return home_goals, away_goals
    return 0, 0


def _initial_rows(data: WorldCupData) -> Dict[str, Dict[str, dict]]:
    rows: Dict[str, Dict[str, dict]] = {}
    for team in data.teams:
        team_id = str(team.get("team_id") or "")
        if not team_id:
            continue
        group_name = str(team.get("group") or "").upper()
        rating = data.ratings.get(team_id, {})
        rows.setdefault(group_name, {})[team_id] = {
            "team_id": team_id,
            "team_name": team_public_name(team),
            "group": group_name,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_difference": 0,
            "points": 0,
            "elo": float(rating.get("elo") or 1800),
            "fifa_rank": rating.get("fifa_rank"),
        }
    return rows


def _team_map(data: WorldCupData) -> Dict[str, dict]:
    return {str(team.get("team_id")): deepcopy(team) for team in data.teams if team.get("team_id")}


def _apply_score(row: dict, goals_for: int, goals_against: int) -> None:
    row["played"] += 1
    row["goals_for"] += goals_for
    row["goals_against"] += goals_against
    row["goal_difference"] = row["goals_for"] - row["goals_against"]
    if goals_for > goals_against:
        row["wins"] += 1
        row["points"] += 3
    elif goals_for == goals_against:
        row["draws"] += 1
        row["points"] += 1
    else:
        row["losses"] += 1


def _safe_trials(trials: int) -> int:
    try:
        value = int(trials)
    except (TypeError, ValueError):
        value = 2000
    return max(1, min(value, 10000))
