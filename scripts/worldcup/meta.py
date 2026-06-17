from __future__ import annotations

from datetime import datetime, timezone

from .data_loader import WorldCupData
from .fixture_status import describe_fixture_status


def build_worldcup_meta(data: WorldCupData) -> dict:
    fixtures = data.fixtures
    groups = sorted({str(team.get("group") or "").upper() for team in data.teams if team.get("group")})
    now = datetime.now(timezone.utc)
    status_rows = [describe_fixture_status(item, now=now) for item in fixtures]
    finished_count = sum(1 for item in status_rows if item["computed_status"] == "finished")
    result_pending_count = sum(1 for item in status_rows if item["computed_status"] == "result_pending")
    scheduled_count = sum(1 for item in status_rows if item["computed_status"] == "scheduled")
    sources = []
    for source in data.sources:
        item = dict(source)
        item["source_url"] = item.get("source_url") or item.get("url") or ""
        item["data_cutoff_at"] = item.get("data_cutoff_at") or data.data_cutoff_at
        sources.append(item)
    return {
        "success": True,
        "data_cutoff_at": data.data_cutoff_at,
        "base_data_cutoff_at": data.base_data_cutoff_at,
        "effective_data_cutoff_at": data.data_cutoff_at,
        "model_version": data.model_version,
        "sources": sources,
        "teams_count": len(data.teams),
        "groups_count": len(groups),
        "fixtures_count": len(fixtures),
        "finished_count": finished_count,
        "scheduled_count": scheduled_count,
        "result_pending_count": result_pending_count,
        "local_patch_applied": data.local_patch_applied,
        "local_patch_matches_count": data.local_patch_matches_count,
        "local_patch_data_cutoff_at": data.local_patch_data_cutoff_at,
        "update_source_mode": data.update_source_mode,
        "is_realtime": False,
        "limitations": [
            "当前版本使用本地手工数据包，不是实时比分；最新赛果可通过“检查在线更新”和“应用赛果更新”补到本机。",
            "已开赛或已结束但缺少赛果的比赛，会显示为“赛果待更新”，不会继续生成赛前预测。",
            "AI 只负责白话解释，不参与概率计算。",
            "概率不代表赛果保证，仅供模型模拟参考。",
        ],
    }
