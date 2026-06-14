from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class TeamAlias:
    team_id: str
    display_name: str
    display_name_zh: str
    aliases: tuple[str, ...]
    group: str | None = None

    def matches(self, name: str) -> bool:
        target = normalize_team_name(name)
        return target in {normalize_team_name(alias) for alias in self.aliases} or target in {
            normalize_team_name(self.team_id),
            normalize_team_name(self.display_name),
            normalize_team_name(self.display_name_zh),
        }


def normalize_team_name(name: str) -> str:
    return ''.join(ch.lower() for ch in (name or '').strip() if ch.isalnum() or '一' <= ch <= '鿿')


def build_alias_map(teams: Iterable[dict]) -> Dict[str, TeamAlias]:
    alias_map: Dict[str, TeamAlias] = {}
    for item in teams:
        aliases = tuple(item.get('aliases') or ())
        team = TeamAlias(
            team_id=str(item.get('team_id') or '').strip(),
            display_name=str(item.get('display_name') or '').strip(),
            display_name_zh=str(item.get('display_name_zh') or '').strip(),
            aliases=aliases,
            group=item.get('group'),
        )
        for key in {team.team_id, team.display_name, team.display_name_zh, *aliases}:
            normalized = normalize_team_name(key)
            if normalized:
                alias_map[normalized] = team
    return alias_map


def resolve_team(name: str, alias_map: Dict[str, TeamAlias]) -> Optional[TeamAlias]:
    normalized = normalize_team_name(name)
    if not normalized:
        return None
    if normalized in alias_map:
        return alias_map[normalized]
    for team in alias_map.values():
        if team.matches(name):
            return team
    return None
