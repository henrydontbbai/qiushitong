import importlib
import os
import unittest


class WorldCupTournamentApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCAL_FREE_MODE"] = "true"
        cls.app_module = importlib.import_module("app")
        cls.app_module.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app_module.app.test_client()

    def test_tournament_endpoint_works_without_database_or_ai_key(self):
        response = self.client.get("/api/worldcup/tournament?trials=20&seed=2026")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["trials"], 20)
        self.assertEqual(len(data["teams"]), 48)
        self.assertIn("round_totals", data)
        self.assertAlmostEqual(data["round_totals"]["champion_probability"], 1.0, places=6)
        self.assertIn("model_version", data)
        self.assertIn("data_cutoff_at", data)
        self.assertIn("概率参考，不代表赛果保证", data["disclaimer"])
        self.assertNotIn("ai_generated", data)

    def test_tournament_endpoint_caps_too_large_trials(self):
        response = self.client.get("/api/worldcup/tournament?trials=999999&seed=2026")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["trials"], 5000)

    def test_tournament_endpoint_rejects_bad_seed(self):
        response = self.client.get("/api/worldcup/tournament?trials=20&seed=bad")

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("seed 必须是数字", data["message"])


if __name__ == "__main__":
    unittest.main()
