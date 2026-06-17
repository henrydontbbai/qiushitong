from __future__ import annotations

from copy import deepcopy
from typing import Dict, Iterable, List

from .data_loader import WorldCupData


GROUP_ORDER = list("ABCDEFGHIJKL")


def team_public_name(team: dict) -> str:
    return team.get("display_name_zh") or team.get("display_name") or team.get("team_id") or ""


def build_group_standings(data: WorldCupData) -> dict:
    """Build current 2026 World Cup group standings from locked finished scores only."""
    groups = _initial_group_rows(data)
    finished_matches = 0
    scheduled_matches = 0

    for fixture in data.fixtures:
        if fixture.get("stage") != "group":
            continue
        status = str(fixture.get("status") or "").lower()
        if status == "finished" and fixture.get("final_score"):
            _apply_finished_fixture(groups, fixture)
            finished_matches += 1
        else:
            scheduled_matches += 1

    ranked_groups = []
    for group_name in sorted(groups.keys(), key=_group_sort_key):
        rows = _rank_rows(groups[group_name].values())
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
        ranked_groups.append({"group": group_name, "teams": rows})

    return {
        "success": True,
        "groups": ranked_groups,
        "summary": {
            "groups_count": len(ranked_groups),
            "teams_count": sum(len(group["teams"]) for group in ranked_groups),
            "finished_matches": finished_matches,
            "scheduled_matches": scheduled_matches,
            "rules": "小组赛当前积分榜；已完赛比分锁定，未赛比赛不计入当前积分。",
        },
        "model_version": data.model_version,
        "data_cutoff_at": data.data_cutoff_at,
        "base_data_cutoff_at": data.base_data_cutoff_at,
        "effective_data_cutoff_at": data.data_cutoff_at,
        "local_patch_applied": data.local_patch_applied,
        "local_patch_matches_count": data.local_patch_matches_count,
        "update_source_mode": data.update_source_mode,
        "disclaimer": "积分榜和出线概率仅供模型模拟参考，概率不代表赛果保证。",
    }


def rank_group_rows(rows: Iterable[dict]) -> List[dict]:
    """Public helper used by the simulator."""
    return _rank_rows(rows)


def best_third_rows(groups: List[dict]) -> List[dict]:
    third_rows = []
    for group in groups:
        teams = group.get("teams", [])
        if len(teams) >= 3:
            row = deepcopy(teams[2])
            row["group"] = group.get("group")
            third_rows.append(row)
    return _rank_rows(third_rows)


def _initial_group_rows(data: WorldCupData) -> Dict[str, Dict[str, dict]]:
    groups: Dict[str, Dict[str, dict]] = {}
    for team in data.teams:
        team_id = str(team.get("team_id") or "")
        if not team_id:
            continue
        group_name = str(team.get("group") or "未分组").upper()
        rating = data.ratings.get(team_id, {})
        groups.setdefault(group_name, {})[team_id] = {
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
    return groups


def _apply_finished_fixture(groups: Dict[str, Dict[str, dict]], fixture: dict) -> None:
    group_name = str(fixture.get("group") or "").upper()
    home_id = str(fixture.get("home_team_id") or "")
    away_id = str(fixture.get("away_team_id") or "")
    score = fixture.get("final_score") or {}
    if group_name not in groups or home_id not in groups[group_name] or away_id not in groups[group_name]:
        return
    home_goals = int(score.get("home", 0))
    away_goals = int(score.get("away", 0))
    _apply_match(groups[group_name][home_id], home_goals, away_goals)
    _apply_match(groups[group_name][away_id], away_goals, home_goals)


def _apply_match(row: dict, goals_for: int, goals_against: int) -> None:
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


def _rank_rows(rows: Iterable[dict]) -> List[dict]:
    return sorted(
        [deepcopy(row) for row in rows],
        key=lambda row: (
            -int(row.get("points", 0)),
            -int(row.get("goal_difference", 0)),
            -int(row.get("goals_for", 0)),
            float(row.get("fifa_rank") or 999),
            -float(row.get("elo") or 0),
            str(row.get("team_id") or ""),
        ),
    )


def _group_sort_key(group_name: str):
    if group_name in GROUP_ORDER:
        return (0, GROUP_ORDER.index(group_name))
    return (1, group_name)
