from __future__ import annotations

from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path
from typing import Iterable, List

from .standings import GROUP_ORDER, best_third_rows


class BracketRuleError(ValueError):
    """Raised when 2026 World Cup bracket rules cannot be applied safely."""


RULES_FILE = "bracket_rules_2026.json"


def load_bracket_rules(data_dir: str | Path) -> dict:
    """Load local FIFA 2026 round-of-32 bracket rules."""
    path = Path(data_dir) / RULES_FILE
    if not path.exists():
        raise BracketRuleError("缺少淘汰赛规则文件 bracket_rules_2026.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BracketRuleError(f"淘汰赛规则文件不是有效 JSON：{exc}") from exc


def validate_bracket_rules(rules: dict, require_all_assignments: bool = True) -> dict:
    """Validate the fixed FIFA 2026 round-of-32 rules and return a public summary."""
    fmt = rules.get("format") or {}
    groups = [str(group).upper() for group in fmt.get("groups", [])]
    if groups != GROUP_ORDER:
        raise BracketRuleError("淘汰赛规则的小组列表必须为 A-L 共 12 组")

    slots = rules.get("round_of_32_slots") or []
    if len(slots) != 16:
        raise BracketRuleError("Round of 32 对阵槽数量必须为 16")
    match_ids = [str(slot.get("match_id") or "") for slot in slots]
    if match_ids != [f"M{number}" for number in range(73, 89)]:
        raise BracketRuleError("Round of 32 对阵槽必须覆盖 M73-M88")

    assignments = rules.get("third_place_assignments") or {}
    expected_keys = {"".join(combo) for combo in combinations(GROUP_ORDER, 8)}
    actual_keys = set(assignments.keys())
    if require_all_assignments and actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        details = []
        if missing:
            details.append(f"缺少 {len(missing)} 个组合，例如 {missing[0]}")
        if extra:
            details.append(f"多出 {len(extra)} 个组合，例如 {extra[0]}")
        raise BracketRuleError("第三名组合映射不完整：" + "；".join(details))

    columns = set(rules.get("third_place_assignment_columns") or [])
    for key, assignment in assignments.items():
        if len(key) != 8 or set(key) - set(GROUP_ORDER):
            raise BracketRuleError(f"第三名组合 {key} 不是 A-L 中的 8 个小组")
        slot_map = assignment.get("slots") or {}
        if set(slot_map.keys()) != columns:
            raise BracketRuleError(f"第三名组合 {key} 的槽位列不完整")
        values = [str(value) for value in slot_map.values()]
        value_groups = [value[1:] for value in values if value.startswith("3")]
        if sorted(value_groups) != sorted(key):
            raise BracketRuleError(f"第三名组合 {key} 的分配球队与组合不一致")

    return {
        "success": True,
        "rules_ready": True,
        "schema_version": rules.get("schema_version"),
        "source_id": rules.get("source_id"),
        "source_name": rules.get("source_name"),
        "source_url": rules.get("source_url"),
        "data_cutoff_at": rules.get("data_cutoff_at"),
        "groups_count": len(groups),
        "teams_per_group": int(fmt.get("teams_per_group") or 4),
        "top_two_qualifiers": int(fmt.get("group_winners") or 0) + int(fmt.get("group_runners_up") or 0),
        "best_third_qualifiers": int(fmt.get("best_third_placed") or 0),
        "round_of_32_slots_count": len(slots),
        "third_place_assignments_count": len(assignments),
        "message": "淘汰赛规则已准备；冠军路径模拟将在下一阶段开放。",
        "disclaimer": "当前仅校验 2026 Round of 32 规则，不计算冠军概率；概率不代表赛果保证。",
    }


def build_round_of_32(standings: dict, data_dir: str | Path, rules: dict | None = None) -> dict:
    """Build the 32-team round-of-32 bracket from ranked group standings."""
    rules = rules or load_bracket_rules(data_dir)
    validate_bracket_rules(rules, require_all_assignments=False)
    groups = standings.get("groups") or []
    grouped_rows = {str(group.get("group") or "").upper(): group.get("teams", []) for group in groups}
    missing_groups = [group for group in GROUP_ORDER if group not in grouped_rows]
    if missing_groups:
        raise BracketRuleError("小组积分数据不完整，缺少：" + "、".join(missing_groups))

    direct_slots = {}
    for group_name in GROUP_ORDER:
        rows = grouped_rows.get(group_name) or []
        if len(rows) < 3:
            raise BracketRuleError(f"{group_name} 组至少需要前三名才能生成 32 强")
        direct_slots[f"1{group_name}"] = _team_slot(rows[0], f"1{group_name}")
        direct_slots[f"2{group_name}"] = _team_slot(rows[1], f"2{group_name}")

    third_rows = best_third_rows(groups)[:8]
    third_groups = "".join(sorted(str(row.get("group") or "").upper() for row in third_rows))
    assignment = (rules.get("third_place_assignments") or {}).get(third_groups)
    if not assignment:
        raise BracketRuleError(f"缺少小组第三组合 {third_groups} 的 Round of 32 映射")

    third_by_group = {str(row.get("group") or "").upper(): _team_slot(row, f"3{str(row.get('group') or '').upper()}") for row in third_rows}
    assigned_thirds = {}
    for column, third_slot in (assignment.get("slots") or {}).items():
        group_name = str(third_slot)[1:]
        if group_name not in third_by_group:
            raise BracketRuleError(f"小组第三映射 {column}->{third_slot} 找不到对应球队")
        assigned_thirds[column] = third_by_group[group_name]

    matches = []
    used_team_ids = set()
    for slot in rules.get("round_of_32_slots") or []:
        team_a = _resolve_participant(slot.get("team_a") or {}, direct_slots, assigned_thirds)
        team_b = _resolve_participant(slot.get("team_b") or {}, direct_slots, assigned_thirds)
        for team in [team_a, team_b]:
            team_id = team.get("team_id")
            if team_id in used_team_ids:
                raise BracketRuleError(f"32 强对阵出现重复球队：{team.get('team_name') or team_id}")
            used_team_ids.add(team_id)
        matches.append(
            {
                "match_id": slot.get("match_id"),
                "team_a": team_a,
                "team_b": team_b,
            }
        )

    if len(used_team_ids) != 32:
        raise BracketRuleError("32 强对阵必须包含 32 支不同球队")

    return {
        "success": True,
        "matches": matches,
        "third_place_combination": third_groups,
        "third_place_assignment_option": assignment.get("option"),
        "rules_summary": validate_bracket_rules(rules),
        "disclaimer": "当前仅生成 Round of 32 对阵规则基线，不计算冠军概率。",
    }


def _resolve_participant(ref: dict, direct_slots: dict, assigned_thirds: dict) -> dict:
    ref_type = ref.get("type")
    if ref_type == "rank":
        slot = str(ref.get("slot") or "")
        if slot not in direct_slots:
            raise BracketRuleError(f"找不到直接晋级槽位 {slot}")
        return deepcopy(direct_slots[slot])
    if ref_type == "third":
        column = str(ref.get("column") or "")
        if column not in assigned_thirds:
            raise BracketRuleError(f"找不到小组第三槽位 {column}")
        return deepcopy(assigned_thirds[column])
    raise BracketRuleError("未知的 Round of 32 对阵槽类型")


def _team_slot(row: dict, qualification_slot: str) -> dict:
    return {
        "team_id": str(row.get("team_id") or ""),
        "team_name": row.get("team_name") or row.get("display_name_zh") or row.get("display_name") or row.get("team_id") or "",
        "group": str(row.get("group") or "").upper(),
        "qualification_slot": qualification_slot,
    }
