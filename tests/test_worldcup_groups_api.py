import importlib
import os
import unittest


class WorldCupGroupsApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCAL_FREE_MODE"] = "true"
        cls.app_module = importlib.import_module("app")
        cls.app_module.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app_module.app.test_client()

    def test_meta_endpoint_exposes_data_sources_without_database_or_ai(self):
        response = self.client.get("/api/worldcup/meta")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["teams_count"], 48)
        self.assertEqual(data["groups_count"], 12)
        self.assertEqual(data["fixtures_count"], 72)
        self.assertIn("model_version", data)
        self.assertGreaterEqual(len(data["sources"]), 1)
        self.assertIn("source_url", data["sources"][0])
        self.assertIn("data_cutoff_at", data["sources"][0])
        self.assertFalse(data["is_realtime"])
        self.assertIn("result_pending_count", data)
        self.assertTrue(any("不是实时比分" in item for item in data["limitations"]))

    def test_groups_endpoint_returns_current_standings(self):
        response = self.client.get("/api/worldcup/groups")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["groups"]), 12)
        self.assertIn("base_data_cutoff_at", data)
        self.assertIn("effective_data_cutoff_at", data)
        self.assertIn("local_patch_applied", data)
        self.assertIn("local_patch_matches_count", data)
        self.assertEqual(data["data_cutoff_at"], data["effective_data_cutoff_at"])
        group = data["groups"][0]
        self.assertIn("group", group)
        self.assertEqual(len(group["teams"]), 4)
        self.assertIn("points", group["teams"][0])
        self.assertIsNone(data.get("simulation"))

    def test_groups_endpoint_can_include_small_seeded_simulation(self):
        response = self.client.get("/api/worldcup/groups?simulate=1&trials=30&seed=123")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("effective_data_cutoff_at", data)
        self.assertEqual(data["data_cutoff_at"], data["effective_data_cutoff_at"])
        self.assertIsNotNone(data["simulation"])
        self.assertEqual(data["simulation"]["trials"], 30)
        simulated_teams = [team for group in data["simulation"]["groups"] for team in group["teams"]]
        self.assertEqual(len(simulated_teams), 48)
        qualify_total = sum(team["qualify_probability"] for team in simulated_teams)
        self.assertAlmostEqual(qualify_total, 32.0, places=6)


if __name__ == "__main__":
    unittest.main()
