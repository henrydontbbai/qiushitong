import importlib
import os
import unittest
from unittest import mock


class WorldCupUpdateApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LOCAL_FREE_MODE"] = "true"
        cls.app_module = importlib.import_module("app")
        cls.app_module.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app_module.app.test_client()

    def test_update_status_endpoint_works_without_database_or_ai_key(self):
        response = self.client.get("/api/worldcup/update-status")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertIn("base_data_cutoff_at", data)
        self.assertIn("effective_data_cutoff_at", data)
        self.assertIn("result_pending_count", data)
        self.assertIn("display_status", data)

    def test_check_update_endpoint_returns_preview(self):
        payload = {
            "success": True,
            "update_available": True,
            "skipped_due_to_cooldown": False,
            "checked_source": {"source_id": "github_raw_fallback", "name": "GitHub"},
            "available_update": {
                "source_id": "worldcup_results_patch_20260616",
                "published_at": "2026-06-16T09:00:00+08:00",
                "data_cutoff_at": "2026-06-16T09:00:00+08:00",
                "matches_count": 7,
            },
            "message": "发现 7 场可更新赛果",
        }
        with mock.patch.object(self.app_module, "check_worldcup_update", return_value=payload):
            response = self.client.post("/api/worldcup/check-update", json={"auto": True})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["update_available"])
        self.assertEqual(data["available_update"]["matches_count"], 7)

    def test_apply_update_endpoint_returns_refresh_summary(self):
        payload = {
            "success": True,
            "updated_matches_count": 7,
            "effective_data_cutoff_at": "2026-06-16T09:00:00+08:00",
            "result_pending_count": 3,
            "message": "已更新 7 场赛果",
        }
        with mock.patch.object(self.app_module, "apply_worldcup_update", return_value=payload):
            response = self.client.post("/api/worldcup/apply-update")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["updated_matches_count"], 7)
        self.assertEqual(data["result_pending_count"], 3)

    def test_apply_update_no_newer_patch_returns_info_instead_of_gateway_error(self):
        payload = {
            "success": False,
            "error_code": "NO_NEWER_UPDATE",
            "message": "当前在线补丁不比本机补丁更新，已保留现有赛果。",
        }
        with mock.patch.object(self.app_module, "apply_worldcup_update", return_value=payload):
            response = self.client.post("/api/worldcup/apply-update")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_code"], "NO_NEWER_UPDATE")

    def test_check_update_failure_uses_user_friendly_message(self):
        payload = {
            "success": False,
            "error_code": "UPDATE_SOURCE_UNREACHABLE",
            "message": "暂时连不上更新源，继续使用本机数据。你仍可查看本地预测，稍后再点“检查在线更新”即可。",
            "technical_detail": "GitHub Raw: tls failed",
            "update_available": False,
            "skipped_due_to_cooldown": False,
        }
        with mock.patch.object(self.app_module, "check_worldcup_update", return_value=payload):
            response = self.client.post("/api/worldcup/check-update", json={"auto": False})

        self.assertEqual(response.status_code, 502)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error_code"], "UPDATE_SOURCE_UNREACHABLE")
        self.assertIn("暂时连不上更新源", data["message"])
        self.assertIn("technical_detail", data)

    def test_check_update_failure_can_report_remote_file_not_published(self):
        payload = {
            "success": False,
            "error_code": "UPDATE_SOURCE_UNREACHABLE",
            "message": "在线更新源已连接，但最新赛果补丁文件还未发布，当前继续使用本机数据。",
            "technical_detail": "GitHub Raw: 404 Not Found",
            "update_available": False,
            "skipped_due_to_cooldown": False,
        }
        with mock.patch.object(self.app_module, "check_worldcup_update", return_value=payload):
            response = self.client.post("/api/worldcup/check-update", json={"auto": False})

        self.assertEqual(response.status_code, 502)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("还未发布", data["message"])


if __name__ == "__main__":
    unittest.main()
