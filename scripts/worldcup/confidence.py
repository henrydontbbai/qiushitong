from __future__ import annotations


def derive_data_quality(has_rating: bool, has_fixture: bool, has_cutoff: bool, has_alias: bool = True) -> dict:
    score = sum([has_rating, has_fixture, has_cutoff, has_alias])
    if score >= 4:
        level = 'high'
    elif score >= 3:
        level = 'medium'
    else:
        level = 'low'
    return {'level': level, 'score': score, 'max_score': 4}
