from __future__ import annotations

from .data_loader import WorldCupData


def build_worldcup_meta(data: WorldCupData) -> dict:
    fixtures = data.fixtures
    groups = sorted({str(team.get("group") or "").upper() for team in data.teams if team.get("group")})
    finished_count = sum(1 for item in fixtures if str(item.get("status") or "").lower() == "finished")
    scheduled_count = sum(1 for item in fixtures if str(item.get("status") or "").lower() != "finished")
    sources = []
    for source in data.sources:
        item = dict(source)
        item["source_url"] = item.get("source_url") or item.get("url") or ""
        item["data_cutoff_at"] = item.get("data_cutoff_at") or data.data_cutoff_at
        sources.append(item)
    return {
        "success": True,
        "data_cutoff_at": data.data_cutoff_at,
        "model_version": data.model_version,
        "sources": sources,
        "teams_count": len(data.teams),
        "groups_count": len(groups),
        "fixtures_count": len(fixtures),
        "finished_count": finished_count,
        "scheduled_count": scheduled_count,
        "limitations": [
            "当前版本只覆盖世界杯小组赛本地手工数据，不含淘汰赛对阵和冠军概率。",
            "AI 只负责白话解释，不参与概率计算。",
            "概率不代表赛果保证，仅供模型模拟参考。",
        ],
    }
