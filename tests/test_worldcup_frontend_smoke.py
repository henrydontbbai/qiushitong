from pathlib import Path
import unittest


class WorldCupFrontendSmokeTest(unittest.TestCase):
    def test_worldcup_frontend_entry_and_script_are_present(self):
        html = Path("templates/index.html").read_text(encoding="utf-8")
        js = Path("static/js/worldcup.js").read_text(encoding="utf-8")

        self.assertIn("世界杯专题", html)
        self.assertIn("worldcup-mode-btn", html)
        self.assertIn("worldcup-mode", html)
        self.assertIn("js/worldcup.js", html)
        self.assertIn("v='phase-d0'", html)
        self.assertIn("概率不代表赛果保证", html)
        self.assertIn("worldcup-meta-panel", html)
        self.assertIn("worldcup-groups-panel", html)
        self.assertIn("worldcup-bracket-panel", html)
        self.assertNotIn("????", html)

        for text in [
            "胜",
            "平",
            "负",
            "预期进球",
            "Top 5",
            "数据完整度",
            "模型版本",
            "概率不代表赛果保证",
            "/api/worldcup/meta",
            "/api/worldcup/groups?simulate=1",
            "/api/worldcup/bracket-rules",
            "小组出线概率",
            "淘汰赛规则已准备",
            "冠军路径模拟将在下一阶段开放",
            "event.target.closest('.worldcup-predict-btn')",
        ]:
            self.assertIn(text, js)
        self.assertNotIn("冠军概率表", js)


if __name__ == "__main__":
    unittest.main()
