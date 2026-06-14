from __future__ import annotations


def normalize_market_odds(odds: dict | None) -> dict | None:
    if not odds:
        return None
    home = float(odds.get('home') or odds.get('h') or 0)
    draw = float(odds.get('draw') or odds.get('d') or 0)
    away = float(odds.get('away') or odds.get('a') or 0)
    if home <= 0 or draw <= 0 or away <= 0:
        return None
    implied = [1 / home, 1 / draw, 1 / away]
    total = sum(implied) or 1.0
    return {
        'home_win': round(implied[0] / total, 6),
        'draw': round(implied[1] / total, 6),
        'away_win': round(implied[2] / total, 6),
        'source': 'user_input',
    }
