from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_kickoff_at(value: Any) -> datetime | None:
    """Parse an ISO kickoff time and keep timezone information when present."""
    if not value:
        return None
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def describe_fixture_status(fixture: dict, now: datetime | None = None) -> dict:
    """Return user-facing lifecycle state for a fixture.

    Local World Cup data is a manually maintained snapshot, not a live score feed.
    If kickoff time has passed but no final score is available, the match should
    not be shown as a pre-match prediction opportunity.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    raw_status = str(fixture.get("status") or "").lower()
    final_score = fixture.get("final_score")
    kickoff_at = parse_kickoff_at(fixture.get("kickoff_at"))

    if raw_status == "finished" and final_score:
        return {
            "computed_status": "finished",
            "status_label": "已完赛",
            "action_label": "查看赛果",
            "can_predict": False,
            "can_view_result": True,
            "needs_result_update": False,
            "note": f"已完赛：{final_score.get('home')}-{final_score.get('away')}",
        }

    if kickoff_at and kickoff_at <= now:
        return {
            "computed_status": "result_pending",
            "status_label": "赛果待更新",
            "action_label": "赛果待更新",
            "can_predict": False,
            "can_view_result": False,
            "needs_result_update": True,
            "note": "这场比赛已开赛或已结束，但本地数据包还没有赛果；为避免误导，暂不生成赛前预测。",
        }

    return {
        "computed_status": "scheduled",
        "status_label": "未开赛",
        "action_label": "查看赛前预测",
        "can_predict": True,
        "can_view_result": False,
        "needs_result_update": False,
        "note": "未开赛比赛可查看模型概率参考。",
    }
