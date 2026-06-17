import importlib
import os
import unittest


class WorldCupApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCAL_FREE_MODE"] = "true"
        cls.app_module = importlib.import_module("app")
        cls.app_module.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app_module.app.test_client()

    def test_fixtures_endpoint_works_without_database_or_ai_key(self):
        response = self.client.get("/api/worldcup/fixtures")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["fixtures"]), 1)
        self.assertIn("base_data_cutoff_at", data)
        self.assertIn("effective_data_cutoff_at", data)
        self.assertIn("local_patch_applied", data)
        self.assertIn("local_patch_matches_count", data)
        self.assertEqual(data["data_cutoff_at"], data["effective_data_cutoff_at"])
        fixture = data["fixtures"][0]
        for key in ["match_id", "home_team", "away_team", "kickoff_at", "stage", "status", "data_cutoff_at"]:
            self.assertIn(key, fixture)

    def test_predict_endpoint_works_without_ai_key(self):
        fixtures = self.client.get("/api/worldcup/fixtures").get_json()["fixtures"]
        match_id = next(item["match_id"] for item in fixtures if item.get("can_predict"))

        response = self.client.post("/api/worldcup/predict", json={"match_id": match_id})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        for key in ["probabilities", "expected_goals", "top_scores", "data_quality", "model_version", "data_cutoff_at", "disclaimer"]:
            self.assertIn(key, data)
        probs = data["probabilities"]
        self.assertAlmostEqual(probs["home_win"] + probs["draw"] + probs["away_win"], 1.0, places=4)
        top_scores = data["top_scores"]
        self.assertEqual(top_scores, sorted(top_scores, key=lambda item: item["probability"], reverse=True))
        self.assertIn("概率不代表赛果保证", data["disclaimer"])

    def test_past_unscored_fixture_is_marked_as_result_pending(self):
        fixtures = self.client.get("/api/worldcup/fixtures").get_json()["fixtures"]
        pending = [item for item in fixtures if item.get("needs_result_update")]

        self.assertGreaterEqual(len(pending), 1)
        self.assertFalse(pending[0]["can_predict"])
        self.assertEqual(pending[0]["computed_status"], "result_pending")
        self.assertIn("赛果待更新", pending[0]["status_label"])

    def test_explain_endpoint_falls_back_without_ai_key(self):
        prediction = self.client.post("/api/worldcup/predict", json={"home_team": "Brazil", "away_team": "Germany"}).get_json()

        response = self.client.post("/api/worldcup/explain", json={"prediction": prediction})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertFalse(data["ai_available"])
        self.assertTrue(data["fallback_used"])
        self.assertIn("概率参考", data["explanation"])


if __name__ == "__main__":
    unittest.main()
