import tempfile
import unittest
from pathlib import Path


class WorldCupCoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        (self.data_dir / "teams.json").write_text(
            '''{
  "teams": [
    {"team_id": "BRA", "display_name": "Brazil", "display_name_zh": "巴西", "aliases": ["Brazil", "BRA", "巴西"], "group": "A"},
    {"team_id": "GER", "display_name": "Germany", "display_name_zh": "德国", "aliases": ["Germany", "GER", "德国"], "group": "A"},
    {"team_id": "JPN", "display_name": "Japan", "display_name_zh": "日本", "aliases": ["Japan", "JPN", "日本"], "group": "A"},
    {"team_id": "USA", "display_name": "United States", "display_name_zh": "美国", "aliases": ["United States", "USA", "美国"], "group": "A"}
  ]
}
''',
            encoding="utf-8",
        )
        (self.data_dir / "fixtures_2026.json").write_text(
            '''{
  "fixtures": [
    {"match_id": "WC2026-A-001", "home_team_id": "BRA", "away_team_id": "GER", "kickoff_at": "2026-06-15T03:00:00+08:00", "stage": "group", "group": "A", "venue": "Example Stadium", "neutral_site": true, "status": "scheduled", "final_score": null, "source_id": "fixture-test"},
    {"match_id": "WC2026-A-002", "home_team_id": "JPN", "away_team_id": "USA", "kickoff_at": "2026-06-16T03:00:00+08:00", "stage": "group", "group": "A", "venue": "Example Stadium", "neutral_site": true, "status": "finished", "final_score": {"home": 2, "away": 1}, "source_id": "fixture-test"}
  ]
}
''',
            encoding="utf-8",
        )
        (self.data_dir / "team_ratings.json").write_text(
            '''{
  "data_cutoff_at": "2026-06-11",
  "ratings": [
    {"team_id": "BRA", "elo": 2140, "fifa_rank": 2},
    {"team_id": "GER", "elo": 1980, "fifa_rank": 10},
    {"team_id": "JPN", "elo": 1840, "fifa_rank": 18},
    {"team_id": "USA", "elo": 1790, "fifa_rank": 22}
  ]
}
''',
            encoding="utf-8",
        )
        (self.data_dir / "data_sources.json").write_text(
            '''{
  "sources": [{"source_id": "fixture-test", "name": "Test Fixture", "license_status": "test-only"}],
  "data_cutoff_at": "2026-06-14T00:00:00+08:00"
}
''',
            encoding="utf-8",
        )
        (self.data_dir / "model_versions.json").write_text(
            '''{
  "active_model_version": "wc-elo-poisson-0.1.0",
  "models": [{"version": "wc-elo-poisson-0.1.0", "description": "Test model"}]
}
''',
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_predict_fixture_returns_transparent_probabilities_and_top_scores(self):
        from scripts.worldcup.predictor import WorldCupPredictor

        predictor = WorldCupPredictor(data_dir=self.data_dir)
        result = predictor.predict_fixture("WC2026-A-001")

        self.assertTrue(result["success"])
        probs = result["probabilities"]
        self.assertAlmostEqual(probs["home_win"] + probs["draw"] + probs["away_win"], 1.0, places=4)
        self.assertGreater(probs["home_win"], probs["away_win"])
        self.assertIn("expected_goals", result)
        self.assertEqual(len(result["top_scores"]), 5)
        self.assertGreaterEqual(result["top_scores"][0]["probability"], result["top_scores"][1]["probability"])
        self.assertEqual(result["model_version"], "wc-elo-poisson-0.1.0")
        self.assertIn("概率不代表赛果保证", result["disclaimer"])
        self.assertIn("data_quality", result)

    def test_finished_fixture_is_locked_to_real_score(self):
        from scripts.worldcup.predictor import WorldCupPredictor

        predictor = WorldCupPredictor(data_dir=self.data_dir)
        result = predictor.predict_fixture("WC2026-A-002")

        self.assertTrue(result["success"])
        self.assertTrue(result["locked_result"])
        self.assertEqual(result["final_score"], {"home": 2, "away": 1})
        self.assertIn("已完赛", result["summary"])

    def test_unknown_team_returns_friendly_error(self):
        from scripts.worldcup.predictor import WorldCupPredictor

        predictor = WorldCupPredictor(data_dir=self.data_dir)
        result = predictor.predict_match("不存在球队", "Brazil")

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "UNKNOWN_TEAM")
        self.assertIn("未找到球队", result["message"])

    def test_market_probabilities_are_optional_and_normalized(self):
        from scripts.worldcup.predictor import WorldCupPredictor

        predictor = WorldCupPredictor(data_dir=self.data_dir)
        result = predictor.predict_fixture("WC2026-A-001", odds={"home": 2.0, "draw": 3.5, "away": 4.0})

        self.assertTrue(result["success"])
        market = result["market_probabilities"]
        self.assertAlmostEqual(market["home_win"] + market["draw"] + market["away_win"], 1.0, places=4)
        self.assertEqual(market["source"], "user_input")


if __name__ == "__main__":
    unittest.main()
