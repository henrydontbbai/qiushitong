from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping

from .metrics import brier_score, expected_calibration_error, log_loss, ranked_probability_score


class EvaluationError(ValueError):
    """Raised when evaluation data would create invalid or leaky scoring."""


def _parse_time(value: str, field_name: str) -> datetime:
    if not value:
        raise EvaluationError(f"缺少 {field_name}")
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvaluationError(f"{field_name} 时间格式无效") from exc


def _load_matches(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        return list(payload.get("matches", []))
    if isinstance(payload, list):
        return payload
    raise EvaluationError("评估样本文件格式无效")


def _validate_no_leakage(match: Mapping) -> None:
    kickoff = _parse_time(str(match.get("kickoff_at", "")), "kickoff_at")
    predicted_at = _parse_time(str(match.get("predicted_at", "")), "predicted_at")
    data_cutoff = _parse_time(str(match.get("data_cutoff_at", "")), "data_cutoff_at")
    if predicted_at >= kickoff:
        raise EvaluationError(f"{match.get('match_id', 'unknown')} 的预测时间晚于或等于开赛时间，拒绝评分")
    if data_cutoff >= kickoff:
        raise EvaluationError(f"{match.get('match_id', 'unknown')} 的数据截止时间晚于或等于开赛时间，拒绝评分")


def evaluate_match_rows(matches: Iterable[Mapping], bucket_count: int = 10) -> dict:
    scored = []
    skipped = []
    for match in matches:
        actual_result = match.get("actual_result")
        if not actual_result:
            skipped.append({"match_id": match.get("match_id"), "reason": "缺少真实结果，暂不评分"})
            continue
        _validate_no_leakage(match)
        probabilities = match.get("probabilities") or {}
        scored.append({
            "match_id": match.get("match_id"),
            "probabilities": probabilities,
            "actual_result": actual_result,
            "brier_score": brier_score(probabilities, str(actual_result)),
            "log_loss": log_loss(probabilities, str(actual_result)),
            "rps": ranked_probability_score(probabilities, str(actual_result)),
        })

    metrics = {
        "brier_score": round(mean(item["brier_score"] for item in scored), 6) if scored else None,
        "log_loss": round(mean(item["log_loss"] for item in scored), 6) if scored else None,
        "rps": round(mean(item["rps"] for item in scored), 6) if scored else None,
    }
    calibration = expected_calibration_error(scored, bucket_count=bucket_count) if scored else {
        "bucket_count": bucket_count,
        "sample_count": 0,
        "ece": None,
        "buckets": [],
    }
    return {
        "available": True,
        "sample_count": len(scored),
        "skipped_count": len(skipped),
        "metrics": metrics,
        "calibration": calibration,
        "scored_matches": scored,
        "skipped_matches": skipped,
        "methodology": "离线评估只使用开赛前已生成的概率样本；predicted_at 和 data_cutoff_at 必须早于 kickoff_at。",
        "disclaimer": "模型历史评估只是概率参考，不代表未来赛果保证，也不是投注建议。",
    }


def evaluate_matches(path: str | Path, bucket_count: int = 10) -> dict:
    return evaluate_match_rows(_load_matches(Path(path)), bucket_count=bucket_count)


def load_evaluation_report(data_dir: str | Path) -> dict:
    data_dir = Path(data_dir)
    report_path = data_dir / "evaluation_report.json"
    if not report_path.exists():
        return {
            "available": False,
            "message": "暂无模型历史评估报告；基础预测不受影响。",
            "disclaimer": "模型历史评估只是概率参考，不代表未来赛果保证，也不是投注建议。",
        }
    payload = json.loads(report_path.read_text(encoding="utf-8-sig"))
    payload.setdefault("available", True)
    payload.setdefault("disclaimer", "模型历史评估只是概率参考，不代表未来赛果保证，也不是投注建议。")
    return payload

