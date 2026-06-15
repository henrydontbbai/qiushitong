import unittest

from scripts.worldcup.data_loader import WorldCupData


class WorldCupStandingsTest(unittest.TestCase):
    def test_current_group_standings_lock_finished_scores(self):
        from scripts.worldcup.standings import build_group_standings

        data = WorldCupData(
            teams=[
                {"team_id": "BRA", "display_name": "Brazil", "display_name_zh": "巴西", "group": "A"},
                {"team_id": "GER", "display_name": "Germany", "display_name_zh": "德国", "group": "A"},
                {"team_id": "JPN", "display_name": "Japan", "display_name_zh": "日本", "group": "A"},
                {"team_id": "USA", "display_name": "United States", "display_name_zh": "美国", "group": "A"},
            ],
            fixtures=[
                {
                    "match_id": "A-1",
                    "home_team_id": "BRA",
                    "away_team_id": "GER",
                    "stage": "group",
                    "group": "A",
                    "status": "finished",
                    "final_score": {"home": 2, "away": 1},
                },
                {
                    "match_id": "A-2",
                    "home_team_id": "JPN",
                    "away_team_id": "USA",
                    "stage": "group",
                    "group": "A",
                    "status": "scheduled",
                    "final_score": None,
                },
            ],
            ratings={
                "BRA": {"team_id": "BRA", "elo": 2140, "fifa_rank": 2},
                "GER": {"team_id": "GER", "elo": 1980, "fifa_rank": 10},
                "JPN": {"team_id": "JPN", "elo": 1840, "fifa_rank": 18},
                "USA": {"team_id": "USA", "elo": 1790, "fifa_rank": 22},
            },
            alias_map={},
            data_cutoff_at="2026-06-14T00:00:00+08:00",
            model_version="test-model",
            sources=[],
        )

        result = build_group_standings(data)

        self.assertTrue(result["success"])
        self.assertEqual(result["summary"]["groups_count"], 1)
        self.assertEqual(result["summary"]["finished_matches"], 1)
        self.assertEqual(result["summary"]["scheduled_matches"], 1)
        group = result["groups"][0]
        rows = {row["team_id"]: row for row in group["teams"]}
        self.assertEqual(group["group"], "A")
        self.assertEqual(group["teams"][0]["team_id"], "BRA")
        self.assertEqual(rows["BRA"]["points"], 3)
        self.assertEqual(rows["BRA"]["goals_for"], 2)
        self.assertEqual(rows["BRA"]["goals_against"], 1)
        self.assertEqual(rows["BRA"]["goal_difference"], 1)
        self.assertEqual(rows["GER"]["points"], 0)
        self.assertEqual(rows["JPN"]["played"], 0)

    def test_meta_helper_keeps_sources_and_limitations_in_core_module(self):
        from scripts.worldcup.meta import build_worldcup_meta

        data = WorldCupData(
            teams=[
                {"team_id": "BRA", "group": "A"},
                {"team_id": "GER", "group": "A"},
            ],
            fixtures=[
                {"stage": "group", "status": "finished"},
                {"stage": "group", "status": "scheduled"},
            ],
            ratings={},
            alias_map={},
            data_cutoff_at="2026-06-14T00:00:00+08:00",
            model_version="test-model",
            sources=[{"source_id": "fixture-test", "url": "https://example.com"}],
        )

        result = build_worldcup_meta(data)

        self.assertTrue(result["success"])
        self.assertEqual(result["teams_count"], 2)
        self.assertEqual(result["groups_count"], 1)
        self.assertEqual(result["finished_count"], 1)
        self.assertEqual(result["scheduled_count"], 1)
        self.assertEqual(result["sources"][0]["source_url"], "https://example.com")
        self.assertTrue(any("概率不代表赛果保证" in item for item in result["limitations"]))


if __name__ == "__main__":
    unittest.main()
