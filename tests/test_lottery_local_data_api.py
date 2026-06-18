import importlib
import os
import unittest
from unittest.mock import patch


class LotteryLocalDataApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCAL_FREE_MODE"] = "true"
        cls.app_module = importlib.import_module("app")
        cls.app_module.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app_module.app.test_client()

    def test_lottery_matches_without_local_settings_returns_beginner_message(self):
        with patch.object(self.app_module, "load_local_settings", return_value={}), \
                patch.object(self.app_module.prediction_db, "get_daily_matches") as get_daily_matches:
            response = self.client.get("/api/lottery/matches?days=3")

        self.assertEqual(response.status_code, 404)
        get_daily_matches.assert_not_called()
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("本机还没有配置体彩数据库", data["message"])
        self.assertIn("不会联网更新", data["message"])
        self.assertIn("世界杯专题基础预测不受影响", data["message"])


if __name__ == "__main__":
    unittest.main()
