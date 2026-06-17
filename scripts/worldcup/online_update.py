from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from .data_loader import WorldCupDataLoader
from .fixture_status import describe_fixture_status


DEFAULT_WORLD_CUP_UPDATE_SOURCES = [
    {
        "source_id": "gitee_raw_primary",
        "name": "Gitee Raw",
        "url": "https://gitee.com/henrydontbbai/qiushitong/raw/main/data/worldcup/results_patch_latest.json",
    },
    {
        "source_id": "github_raw_fallback",
        "name": "GitHub Raw",
        "url": "https://raw.githubusercontent.com/henrydontbbai/qiushitong/main/data/worldcup/results_patch_latest.json",
    },
]

COOLDOWN_MINUTES = 30
PATCH_SCHEMA_VERSION = 1


def default_fetcher(url: str) -> str:
    errors: list[str] = []
    for name, fetch in (
        ("requests", _fetch_via_requests),
        ("urllib", _fetch_via_urllib),
        ("powershell", _fetch_via_powershell),
        ("curl", _fetch_via_curl),
    ):
        try:
            text = fetch(url)
            if text:
                return text
            errors.append(f"{name}: empty response")
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise RuntimeError(" | ".join(errors) if errors else "no fetch strategy available")


def check_worldcup_update(
    data_dir: str | Path,
    runtime_dir: str | Path,
    auto: bool = False,
    fetcher: Callable[[str], str] | None = None,
    sources: list[dict] | None = None,
) -> dict:
    runtime_dir = Path(runtime_dir)
    fetcher = fetcher or default_fetcher
    source_list = _normalized_sources(sources)
    state = _load_update_state(runtime_dir)
    now = _now_iso()
    current_data = WorldCupDataLoader(data_dir, runtime_dir=runtime_dir).load()
    current_patch = _load_local_patch(runtime_dir)

    if auto and _cooldown_active(state):
        return {
            "success": True,
            "skipped_due_to_cooldown": True,
            "update_available": bool(state.get("available_update")),
            "available_update": state.get("available_update"),
            "checked_source": state.get("checked_source"),
            "base_data_cutoff_at": current_data.base_data_cutoff_at,
            "effective_data_cutoff_at": current_data.data_cutoff_at,
            "result_pending_count": _result_pending_count(current_data.fixtures),
            "message": "自动检查冷却中，继续使用上次检查结果。",
        }

    last_error = None
    for source in source_list:
        url = str(source.get("url") or "").strip()
        if not url:
            continue
        try:
            patch_payload = _parse_patch_payload(fetcher(url), data_dir)
            matches_count = len(patch_payload.get("matches", []))
            if matches_count <= 0:
                raise ValueError("远程补丁不包含可更新赛果")
            available = _is_remote_patch_newer(current_patch, patch_payload)
            result = {
                "success": True,
                "skipped_due_to_cooldown": False,
                "update_available": available,
                "available_update": _patch_preview(patch_payload) if available else None,
                "checked_source": {
                    "source_id": source.get("source_id"),
                    "name": source.get("name"),
                    "url": url,
                },
                "base_data_cutoff_at": current_data.base_data_cutoff_at,
                "effective_data_cutoff_at": current_data.data_cutoff_at,
                "result_pending_count": _result_pending_count(current_data.fixtures),
                "message": (
                    f"发现 {matches_count} 场可更新赛果"
                    if available
                    else "当前在线数据没有比本机更新。"
                ),
            }
            _save_update_state(
                runtime_dir,
                {
                    "last_checked_at": now,
                    "last_check_success": True,
                    "last_check_message": result["message"],
                    "checked_source": result["checked_source"],
                    "available_update": result["available_update"],
                },
            )
            return result
        except Exception as exc:
            last_error = f"{source.get('name') or source.get('source_id')}: {exc}"
            continue

    failure = {
        "success": False,
        "skipped_due_to_cooldown": False,
        "update_available": False,
        "available_update": None,
        "checked_source": None,
        "error_code": "UPDATE_SOURCE_UNREACHABLE",
        "base_data_cutoff_at": current_data.base_data_cutoff_at,
        "effective_data_cutoff_at": current_data.data_cutoff_at,
        "result_pending_count": _result_pending_count(current_data.fixtures),
        "message": _friendly_check_failure_message(last_error),
        "technical_detail": last_error or "",
    }
    _save_update_state(
        runtime_dir,
        {
            "last_checked_at": now,
            "last_check_success": False,
            "last_check_message": failure["message"],
            "checked_source": None,
            "available_update": None,
        },
    )
    return failure


def apply_worldcup_update(
    data_dir: str | Path,
    runtime_dir: str | Path,
    fetcher: Callable[[str], str] | None = None,
    sources: list[dict] | None = None,
) -> dict:
    runtime_dir = Path(runtime_dir)
    fetcher = fetcher or default_fetcher
    source_list = _normalized_sources(sources)
    current_patch = _load_local_patch(runtime_dir)

    last_error = None
    for source in source_list:
        url = str(source.get("url") or "").strip()
        if not url:
            continue
        try:
            patch_payload = _parse_patch_payload(fetcher(url), data_dir)
            matches_count = len(patch_payload.get("matches", []))
            if matches_count <= 0:
                raise ValueError("远程补丁不包含可更新赛果")
            if not _is_remote_patch_newer(current_patch, patch_payload):
                return {
                    "success": False,
                    "error_code": "NO_NEWER_UPDATE",
                    "message": "当前在线补丁不比本机补丁更新，已保留现有赛果。",
                }
            _save_patch(runtime_dir, patch_payload)
            refreshed = WorldCupDataLoader(data_dir, runtime_dir=runtime_dir).load()
            result = {
                "success": True,
                "updated_matches_count": matches_count,
                "base_data_cutoff_at": refreshed.base_data_cutoff_at,
                "effective_data_cutoff_at": refreshed.data_cutoff_at,
                "result_pending_count": _result_pending_count(refreshed.fixtures),
                "local_patch_applied": refreshed.local_patch_applied,
                "local_patch_matches_count": refreshed.local_patch_matches_count,
                "message": f"已更新 {matches_count} 场赛果",
                "checked_source": {
                    "source_id": source.get("source_id"),
                    "name": source.get("name"),
                    "url": url,
                },
            }
            _save_update_state(
                runtime_dir,
                {
                    "last_checked_at": _now_iso(),
                    "last_check_success": True,
                    "last_check_message": result["message"],
                    "checked_source": result["checked_source"],
                    "available_update": None,
                },
            )
            return result
        except Exception as exc:
            last_error = f"{source.get('name') or source.get('source_id')}: {exc}"
            continue

    return {
        "success": False,
        "error_code": "UPDATE_SOURCE_UNREACHABLE",
        "message": _friendly_apply_failure_message(last_error),
        "technical_detail": last_error or "",
    }


def _fetch_via_requests(url: str) -> str:
    response = requests.get(url, timeout=20, headers={"User-Agent": "QiuShiTong/1.0"})
    response.raise_for_status()
    return response.text


def _fetch_via_urllib(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "QiuShiTong/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


def _fetch_via_powershell(url: str) -> str:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "$ProgressPreference='SilentlyContinue'; "
            "$headers = @{ 'User-Agent' = 'QiuShiTong/1.0' }; "
            f"$r = Invoke-WebRequest -Uri '{url}' -Headers $headers -UseBasicParsing -TimeoutSec 20; "
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            "Write-Output $r.Content"
        ),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=30, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "powershell fetch failed").strip())
    return result.stdout


def _fetch_via_curl(url: str) -> str:
    command = [
        "curl.exe",
        "-L",
        url,
        "-A",
        "QiuShiTong/1.0",
        "--connect-timeout",
        "20",
        "--max-time",
        "30",
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=40, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "curl fetch failed").strip())
    return result.stdout


def _friendly_check_failure_message(last_error: str | None) -> str:
    if _looks_like_remote_missing_file(last_error):
        return "在线更新源已连接，但最新赛果补丁文件还未发布，当前继续使用本机数据。"
    if _looks_like_patch_validation_error(last_error):
        return "在线更新文件校验失败，继续使用本机数据。你仍可查看本地预测，稍后可再试一次。"
    return "暂时连不上更新源，继续使用本机数据。你仍可查看本地预测，稍后再点“检查在线更新”即可。"


def _friendly_apply_failure_message(last_error: str | None) -> str:
    if _looks_like_remote_missing_file(last_error):
        return "在线赛果更新失败：更新源已连接，但最新赛果补丁文件还未发布，已继续保留本机数据。"
    if _looks_like_patch_validation_error(last_error):
        return "在线赛果更新失败：更新文件校验未通过，已继续保留本机数据。"
    return "在线赛果更新失败：暂时连不上更新源，已继续保留本机数据。"


def _looks_like_patch_validation_error(last_error: str | None) -> bool:
    if not last_error:
        return False
    text = str(last_error)
    markers = [
        "远程补丁",
        "schema_version",
        "matches",
        "match_id",
        "final_score",
        "data_cutoff_at",
        "status 只允许",
        "不包含可更新赛果",
        "格式无效",
    ]
    return any(marker in text for marker in markers)


def _looks_like_remote_missing_file(last_error: str | None) -> bool:
    if not last_error:
        return False
    text = str(last_error)
    markers = [
        "404",
        "未找到",
        "Not Found",
        "404) 未找到",
        "不包含可更新赛果",
    ]
    return any(marker in text for marker in markers)


def build_worldcup_update_status(data_dir: str | Path, runtime_dir: str | Path) -> dict:
    runtime_dir = Path(runtime_dir)
    data = WorldCupDataLoader(data_dir, runtime_dir=runtime_dir).load()
    state = _load_update_state(runtime_dir)
    if state.get("available_update"):
        display_status = "发现可更新"
    elif data.local_patch_applied:
        display_status = "本地补丁已应用"
    elif state.get("last_check_success") is False:
        display_status = "检查失败"
    else:
        display_status = "可能落后"
    return {
        "success": True,
        "display_status": display_status,
        "base_data_cutoff_at": data.base_data_cutoff_at,
        "effective_data_cutoff_at": data.data_cutoff_at,
        "local_patch_applied": data.local_patch_applied,
        "local_patch_matches_count": data.local_patch_matches_count,
        "local_patch_data_cutoff_at": data.local_patch_data_cutoff_at,
        "update_source_mode": data.update_source_mode,
        "result_pending_count": _result_pending_count(data.fixtures),
        "last_checked_at": state.get("last_checked_at"),
        "last_check_success": state.get("last_check_success"),
        "last_check_message": state.get("last_check_message"),
        "checked_source": state.get("checked_source"),
        "available_update": state.get("available_update"),
    }


def _normalized_sources(sources: list[dict] | None) -> list[dict]:
    default_sources = _default_update_sources_from_env()
    source_list = default_sources if sources is DEFAULT_WORLD_CUP_UPDATE_SOURCES else (sources or default_sources)
    return [dict(item) for item in source_list if isinstance(item, dict)]


def _default_update_sources_from_env() -> list[dict]:
    source_list = [dict(item) for item in DEFAULT_WORLD_CUP_UPDATE_SOURCES]
    gitee_url = str(os.environ.get("QIUSHITONG_WORLDCUP_UPDATE_GITEE_URL") or "").strip()
    github_url = str(os.environ.get("QIUSHITONG_WORLDCUP_UPDATE_GITHUB_URL") or "").strip()
    if gitee_url:
        source_list[0]["url"] = gitee_url
    if github_url:
        source_list[1]["url"] = github_url
    return source_list


def _parse_patch_payload(raw_text: str, data_dir: str | Path) -> dict:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"远程补丁 JSON 无法解析：{exc}") from exc
    _validate_patch_payload(payload, data_dir)
    return payload


def _validate_patch_payload(payload: dict, data_dir: str | Path) -> None:
    if not isinstance(payload, dict):
        raise ValueError("远程补丁格式不正确。")
    if int(payload.get("schema_version") or 0) != PATCH_SCHEMA_VERSION:
        raise ValueError("schema_version 必须为 1。")
    matches = payload.get("matches")
    if not isinstance(matches, list):
        raise ValueError("matches 必须是数组。")

    fixtures = WorldCupDataLoader(data_dir).load().fixtures
    valid_match_ids = {str(item.get("match_id")) for item in fixtures if item.get("match_id")}
    seen = set()
    for item in matches:
        if not isinstance(item, dict):
            raise ValueError("matches 内每一项都必须是对象。")
        allowed_keys = {"match_id", "status", "final_score", "data_cutoff_at", "source_id", "source_url"}
        unknown_keys = set(item.keys()) - allowed_keys
        if unknown_keys:
            raise ValueError(f"补丁字段超出允许范围：{','.join(sorted(unknown_keys))}")
        match_id = str(item.get("match_id") or "").strip()
        if not match_id:
            raise ValueError("match_id 不能为空。")
        if match_id in seen:
            raise ValueError(f"match_id 重复：{match_id}")
        if match_id not in valid_match_ids:
            raise ValueError(f"match_id 不存在于内置赛程：{match_id}")
        seen.add(match_id)
        if str(item.get("status") or "").lower() != "finished":
            raise ValueError(f"status 只允许 finished：{match_id}")
        score = item.get("final_score")
        if not isinstance(score, dict):
            raise ValueError(f"final_score 缺失或格式错误：{match_id}")
        for side in ("home", "away"):
            value = score.get(side)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"final_score.{side} 必须是非负整数：{match_id}")
        cutoff = item.get("data_cutoff_at")
        if cutoff and _parse_iso(cutoff) is None:
            raise ValueError(f"data_cutoff_at 格式无效：{match_id}")
    for field in ("published_at", "data_cutoff_at"):
        value = payload.get(field)
        if value and _parse_iso(value) is None:
            raise ValueError(f"{field} 格式无效")


def _is_remote_patch_newer(local_patch: dict, remote_patch: dict) -> bool:
    local_time = _parse_iso(local_patch.get("published_at") or local_patch.get("data_cutoff_at"))
    remote_time = _parse_iso(remote_patch.get("published_at") or remote_patch.get("data_cutoff_at"))
    if remote_time is None:
        return False
    if local_time is None:
        return True
    return remote_time > local_time


def _patch_preview(patch_payload: dict) -> dict:
    return {
        "source_id": patch_payload.get("source_id"),
        "source_url": patch_payload.get("source_url"),
        "published_at": patch_payload.get("published_at"),
        "data_cutoff_at": patch_payload.get("data_cutoff_at"),
        "matches_count": len(patch_payload.get("matches", [])),
    }


def _override_dir(runtime_dir: Path) -> Path:
    return runtime_dir / "worldcup_overrides"


def _patch_path(runtime_dir: Path) -> Path:
    return _override_dir(runtime_dir) / "results_patch_latest.json"


def _state_path(runtime_dir: Path) -> Path:
    return _override_dir(runtime_dir) / "update_state.json"


def _save_patch(runtime_dir: Path, payload: dict) -> None:
    override_dir = _override_dir(runtime_dir)
    override_dir.mkdir(parents=True, exist_ok=True)
    _patch_path(runtime_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_local_patch(runtime_dir: Path) -> dict:
    path = _patch_path(runtime_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_update_state(runtime_dir: Path) -> dict:
    path = _state_path(runtime_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_update_state(runtime_dir: Path, payload: dict) -> None:
    override_dir = _override_dir(runtime_dir)
    override_dir.mkdir(parents=True, exist_ok=True)
    _state_path(runtime_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _result_pending_count(fixtures: list[dict]) -> int:
    now = datetime.now(timezone.utc)
    return sum(1 for item in fixtures if describe_fixture_status(item, now=now)["computed_status"] == "result_pending")


def _cooldown_active(state: dict) -> bool:
    checked_at = _parse_iso(state.get("last_checked_at"))
    if checked_at is None:
        return False
    return checked_at + timedelta(minutes=COOLDOWN_MINUTES) > datetime.now(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
