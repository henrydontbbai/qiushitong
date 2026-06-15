from pathlib import Path
import unittest


class WorldCupBracketRulesTest(unittest.TestCase):
    def test_rules_file_loads_and_validates_fifa_2026_baseline(self):
        from scripts.worldcup.bracket_rules import load_bracket_rules, validate_bracket_rules

        rules = load_bracket_rules(Path("data/worldcup"))
        summary = validate_bracket_rules(rules)

        self.assertTrue(summary["success"])
        self.assertEqual(summary["groups_count"], 12)
        self.assertEqual(summary["top_two_qualifiers"], 24)
        self.assertEqual(summary["best_third_qualifiers"], 8)
        self.assertEqual(summary["round_of_32_slots_count"], 16)
        self.assertEqual(summary["third_place_assignments_count"], 495)
        self.assertIn("source_url", summary)
        self.assertIn("data_cutoff_at", summary)

    def test_third_place_assignments_cover_all_495_group_combinations(self):
        from itertools import combinations
        from scripts.worldcup.bracket_rules import GROUP_ORDER, load_bracket_rules

        rules = load_bracket_rules(Path("data/worldcup"))
        expected = {"".join(combo) for combo in combinations(GROUP_ORDER, 8)}
        actual = set(rules["third_place_assignments"].keys())

        self.assertEqual(len(actual), 495)
        self.assertEqual(actual, expected)

    def test_round_of_32_slots_can_be_generated_without_duplicate_teams(self):
        from scripts.worldcup.bracket_rules import build_round_of_32
        from scripts.worldcup.data_loader import WorldCupDataLoader
        from scripts.worldcup.standings import build_group_standings

        data = WorldCupDataLoader(Path("data/worldcup")).load()
        standings = build_group_standings(data)
        bracket = build_round_of_32(standings, Path("data/worldcup"))

        self.assertTrue(bracket["success"])
        self.assertEqual(len(bracket["matches"]), 16)
        team_ids = []
        for match in bracket["matches"]:
            self.assertIn("match_id", match)
            self.assertIn("team_a", match)
            self.assertIn("team_b", match)
            team_ids.append(match["team_a"]["team_id"])
            team_ids.append(match["team_b"]["team_id"])
        self.assertEqual(len(team_ids), 32)
        self.assertEqual(len(set(team_ids)), 32)
        self.assertNotIn("draw", str(bracket).lower())

    def test_missing_third_place_mapping_returns_clear_chinese_error(self):
        from copy import deepcopy
        from scripts.worldcup.bracket_rules import BracketRuleError, build_round_of_32, load_bracket_rules
        from scripts.worldcup.data_loader import WorldCupDataLoader
        from scripts.worldcup.standings import build_group_standings

        data = WorldCupDataLoader(Path("data/worldcup")).load()
        standings = build_group_standings(data)
        rules = deepcopy(load_bracket_rules(Path("data/worldcup")))
        rules["third_place_assignments"] = {}

        with self.assertRaises(BracketRuleError) as ctx:
            build_round_of_32(standings, Path("data/worldcup"), rules=rules)
        self.assertIn("缺少小组第三组合", str(ctx.exception))

    def test_bracket_rules_api_is_available_without_database_or_ai(self):
        import importlib
        import os

        os.environ["LOCAL_FREE_MODE"] = "true"
        app_module = importlib.import_module("app")
        app_module.app.config["TESTING"] = True
        client = app_module.app.test_client()

        response = client.get("/api/worldcup/bracket-rules")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["rules_ready"])
        self.assertEqual(data["round_of_32_slots_count"], 16)
        self.assertEqual(data["third_place_assignments_count"], 495)
        self.assertIn("冠军路径模拟将在下一阶段开放", data["message"])


if __name__ == "__main__":
    unittest.main()
