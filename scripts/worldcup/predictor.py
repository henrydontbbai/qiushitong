from __future__ import annotations

from pathlib import Path
from typing import Optional

from .confidence import derive_data_quality
from .data_loader import WorldCupDataLoader
from .elo import calculate_elo_adjustment
from .goal_model import estimate_expected_goals, result_probabilities, top_scorelines
from .odds import normalize_market_odds
from .team_aliases import resolve_team


class WorldCupPredictor:
    def __init__(self, data_dir: str | Path):
        self.loader = WorldCupDataLoader(data_dir)
        self.data = self.loader.load()

    def _team_from_id(self, team_id: str) -> Optional[dict]:
        for team in self.data.teams:
            if str(team.get('team_id')) == str(team_id):
                return team
        return None

    def _rating_for(self, team_id: str) -> dict:
        return self.data.ratings.get(str(team_id), {})

    def _resolve_team(self, name: str):
        return resolve_team(name, self.data.alias_map)

    def predict_fixture(self, match_id: str, odds: dict | None = None) -> dict:
        fixture = next((item for item in self.data.fixtures if str(item.get('match_id')) == str(match_id)), None)
        if not fixture:
            return {'success': False, 'error_code': 'FIXTURE_NOT_FOUND', 'message': '未找到这场世界杯比赛'}
        if str(fixture.get('status')) == 'finished' and fixture.get('final_score'):
            return {
                'success': True,
                'match_id': match_id,
                'locked_result': True,
                'final_score': fixture['final_score'],
                'summary': '此比赛已完赛，结果已锁定，不再重新预测。',
                'model_version': self.data.model_version,
                'data_cutoff_at': self.data.data_cutoff_at,
                'disclaimer': '已完赛比分仅作赛果展示，不代表未来预测能力。',
            }

        home_team = self._team_from_id(fixture.get('home_team_id'))
        away_team = self._team_from_id(fixture.get('away_team_id'))
        if not home_team or not away_team:
            return {'success': False, 'error_code': 'UNKNOWN_TEAM', 'message': '球队数据不完整，暂时无法预测'}

        home_rating = self._rating_for(home_team['team_id'])
        away_rating = self._rating_for(away_team['team_id'])
        home_elo = float(home_rating.get('elo') or 1800)
        away_elo = float(away_rating.get('elo') or 1800)
        neutral_site = bool(fixture.get('neutral_site', True))
        home_xg, away_xg = estimate_expected_goals(home_elo, away_elo, neutral_site=neutral_site)
        probabilities = result_probabilities(home_xg, away_xg)
        market_probabilities = normalize_market_odds(odds)
        data_quality = derive_data_quality(bool(home_rating and away_rating), True, bool(self.data.data_cutoff_at), True)
        adjustment = calculate_elo_adjustment(home_elo, away_elo, neutral_site=neutral_site)
        return {
            'success': True,
            'match_id': match_id,
            'fixture': fixture,
            'teams': {
                'home': home_team,
                'away': away_team,
            },
            'probabilities': probabilities,
            'expected_goals': {'home': home_xg, 'away': away_xg},
            'top_scores': top_scorelines(home_xg, away_xg),
            'confidence': data_quality['level'],
            'data_quality': data_quality,
            'model_version': self.data.model_version,
            'data_cutoff_at': self.data.data_cutoff_at,
            'disclaimer': '概率不代表赛果保证，仅供模型模拟参考，非决策建议。AI 只解释已有概率，不参与概率计算。',
            'elo_adjustment': adjustment,
            'market_probabilities': market_probabilities,
        }

    def predict_match(self, home_team: str, away_team: str, odds: dict | None = None) -> dict:
        home = self._resolve_team(home_team)
        away = self._resolve_team(away_team)
        if not home or not away:
            return {'success': False, 'error_code': 'UNKNOWN_TEAM', 'message': '未找到球队，请检查球队名称'}
        fixture = {
            'match_id': f"manual-{home.team_id}-{away.team_id}",
            'home_team_id': home.team_id,
            'away_team_id': away.team_id,
            'neutral_site': True,
            'status': 'scheduled',
        }
        self.data.fixtures = [fixture]
        return self.predict_fixture(fixture['match_id'], odds=odds)
