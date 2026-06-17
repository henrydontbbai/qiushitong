from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .team_aliases import build_alias_map


@dataclass
class WorldCupData:
    teams: List[dict]
    fixtures: List[dict]
    ratings: Dict[str, dict]
    alias_map: Dict[str, object]
    data_cutoff_at: str
    model_version: str
    sources: List[dict]
    base_data_cutoff_at: str = ""
    local_patch_applied: bool = False
    local_patch_matches_count: int = 0
    local_patch_data_cutoff_at: str = ""
    update_source_mode: str = "base_only"


class WorldCupDataLoader:
    def __init__(self, data_dir: str | Path, runtime_dir: str | Path | None = None):
        self.data_dir = Path(data_dir)
        self.runtime_dir = Path(runtime_dir) if runtime_dir else None

    def _read_json(self, name: str, default: Any):
        path = self.data_dir / name
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding='utf-8'))

    def _read_runtime_json(self, path: Path, default: Any):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return default

    def _override_path(self) -> Path | None:
        if not self.runtime_dir:
            return None
        return self.runtime_dir / 'worldcup_overrides' / 'results_patch_latest.json'

    def _pick_latest_cutoff(self, *values: str) -> str:
        latest_text = ""
        latest_time = None
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            parsed = self._parse_iso(text)
            if parsed is None:
                if not latest_text:
                    latest_text = text
                continue
            if latest_time is None or parsed > latest_time:
                latest_time = parsed
                latest_text = text
        return latest_text

    def _parse_iso(self, value: str) -> datetime | None:
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

    def _apply_fixture_patch(self, fixtures: List[dict], patch_payload: dict) -> tuple[List[dict], bool, int, str]:
        if not patch_payload:
            return fixtures, False, 0, ""

        patch_matches = patch_payload.get('matches', [])
        if not isinstance(patch_matches, list) or not patch_matches:
            return fixtures, False, 0, ""

        patch_index = {
            str(item.get('match_id')): item
            for item in patch_matches
            if isinstance(item, dict) and item.get('match_id')
        }
        if not patch_index:
            return fixtures, False, 0, ""

        merged = []
        updated = 0
        for fixture in fixtures:
            item = dict(fixture)
            patch = patch_index.get(str(fixture.get('match_id')))
            if patch:
                for field in ('status', 'final_score', 'data_cutoff_at', 'source_id', 'source_url'):
                    if field in patch:
                        item[field] = patch[field]
                updated += 1
            merged.append(item)
        return merged, updated > 0, updated, str(patch_payload.get('data_cutoff_at') or '')

    def load(self) -> WorldCupData:
        teams_payload = self._read_json('teams.json', {'teams': []})
        fixtures_payload = self._read_json('fixtures_2026.json', {'fixtures': []})
        ratings_payload = self._read_json('team_ratings.json', {'ratings': [], 'data_cutoff_at': ''})
        sources_payload = self._read_json('data_sources.json', {'sources': [], 'data_cutoff_at': ''})
        versions_payload = self._read_json('model_versions.json', {'active_model_version': 'wc-elo-poisson-0.1.0', 'models': []})

        teams = teams_payload.get('teams', [])
        fixtures = fixtures_payload.get('fixtures', [])
        ratings = {str(item['team_id']): item for item in ratings_payload.get('ratings', []) if item.get('team_id')}
        alias_map = build_alias_map(teams)
        base_data_cutoff_at = self._pick_latest_cutoff(
            sources_payload.get('data_cutoff_at'),
            ratings_payload.get('data_cutoff_at'),
        )
        model_version = str(versions_payload.get('active_model_version') or 'wc-elo-poisson-0.1.0')
        sources = sources_payload.get('sources', [])
        patch_payload = {}
        override_path = self._override_path()
        if override_path:
            patch_payload = self._read_runtime_json(override_path, {})
        fixtures, local_patch_applied, local_patch_matches_count, local_patch_data_cutoff_at = self._apply_fixture_patch(fixtures, patch_payload)
        data_cutoff_at = local_patch_data_cutoff_at or base_data_cutoff_at
        return WorldCupData(
            teams=teams,
            fixtures=fixtures,
            ratings=ratings,
            alias_map=alias_map,
            data_cutoff_at=data_cutoff_at,
            base_data_cutoff_at=base_data_cutoff_at,
            model_version=model_version,
            sources=sources,
            local_patch_applied=local_patch_applied,
            local_patch_matches_count=local_patch_matches_count,
            local_patch_data_cutoff_at=local_patch_data_cutoff_at,
            update_source_mode='base_plus_patch' if local_patch_applied else 'base_only',
        )
