from __future__ import annotations

import json
from dataclasses import dataclass
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


class WorldCupDataLoader:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def _read_json(self, name: str, default: Any):
        path = self.data_dir / name
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding='utf-8'))

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
        data_cutoff_at = str(ratings_payload.get('data_cutoff_at') or sources_payload.get('data_cutoff_at') or '')
        model_version = str(versions_payload.get('active_model_version') or 'wc-elo-poisson-0.1.0')
        sources = sources_payload.get('sources', [])
        return WorldCupData(
            teams=teams,
            fixtures=fixtures,
            ratings=ratings,
            alias_map=alias_map,
            data_cutoff_at=data_cutoff_at,
            model_version=model_version,
            sources=sources,
        )
