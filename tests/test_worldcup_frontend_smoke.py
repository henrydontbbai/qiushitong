from pathlib import Path
import unittest


class WorldCupFrontendSmokeTest(unittest.TestCase):
    def test_worldcup_frontend_entry_and_script_are_present(self):
        html = Path("templates/index.html").read_text(encoding="utf-8")
        js = Path("static/js/worldcup.js").read_text(encoding="utf-8")
        lottery_js = Path("static/js/lottery.js").read_text(encoding="utf-8")
        css = Path("static/css/style.css").read_text(encoding="utf-8")

        self.assertIn("\u7403\u52bf\u901a", html)
        self.assertNotIn("AI\u8db3\u7403\u9884\u6d4b", html)
        self.assertNotIn("???", html)
        self.assertIn("worldcup-mode-btn", html)
        self.assertIn("worldcup-mode", html)
        self.assertIn("js/worldcup.js", html)
        self.assertIn("v='phase-d1'", html)
        self.assertIn("worldcup-tournament-panel", html)
        self.assertIn("worldcup-meta-panel", html)
        self.assertIn("worldcup-groups-panel", html)
        self.assertIn("worldcup-bracket-panel", html)
        self.assertIn("worldcup-tournament-panel", html)
        self.assertIn("worldcup-evaluation-panel", html)
        self.assertIn("\u6a21\u578b\u5386\u53f2\u8bc4\u4f30", html)
        self.assertNotIn("????", html)
        for text in [
            "worldcup-live-status-card",
            "worldcup-effective-cutoff",
            "worldcup-data-status",
            "worldcup-result-pending-count",
            "worldcup-readonly-tip",
            "worldcup-check-update-btn",
            "worldcup-apply-update-btn",
            "worldcup-update-actions",
            "\u68c0\u67e5\u5728\u7ebf\u66f4\u65b0",
            "\u5e94\u7528\u8d5b\u679c\u66f4\u65b0",
            "\u91cd\u65b0\u8bfb\u53d6\u672c\u673a\u6570\u636e",
            "\u4e0d\u662f\u5b9e\u65f6\u6bd4\u5206",
        ]:
            self.assertIn(text, html)
        for text in [
            "\u4f53\u5f69\u6570\u636e\u5e93\u6a21\u5f0f",
            "\u91cd\u65b0\u8bfb\u53d6\u672c\u673a\u4f53\u5f69\u6570\u636e",
            "\u672c\u6a21\u5f0f\u53ea\u8bfb\u53d6\u672c\u673a\u6570\u636e\u5e93",
        ]:
            self.assertIn(text, html)
        self.assertNotIn("\u4e2d\u56fd\u4f53\u80b2\u5f69\u7968 - \u5b9e\u65f6\u6bd4\u8d5b", html)
        self.assertNotIn("\u70b9\u51fb\"\u5237\u65b0\u6570\u636e\"\u83b7\u53d6\u6700\u65b0\u6bd4\u8d5b", html)
        self.assertIn("worldcup-update-actions", css)

        for text in [
            "renderProb",
            "renderDataQuality",
            "formatPercent",
            "formatXg",
            "/api/worldcup/meta",
            "/api/worldcup/groups?simulate=1",
            "/api/worldcup/bracket-rules",
            "/api/worldcup/tournament",
            "/api/worldcup/evaluation/report",
            "/api/worldcup/update-status",
            "/api/worldcup/check-update",
            "/api/worldcup/apply-update",
            "loadUpdateStatus",
            "checkOnlineUpdate",
            "applyOnlineUpdate",
            "reloadWorldCupDataAfterUpdate",
            "loadTournament",
            "renderTournament",
            "loadEvaluationReport",
            "renderEvaluationReport",
            "Brier Score",
            "Log Loss",
            "RPS",
            "ECE",
            "champion_probability",
            "round_of_16_probability",
            "event.target.closest('.worldcup-predict-btn')",
            "worldcup-tournament-table",
            "worldcup-tournament",
            "worldcup-readonly-summary",
            "renderPendingResult",
            "getFixtureDisplayState",
            "buildPendingText",
            "\u5386\u53f2\u8bc4\u4f30\u4ec5\u4f9b\u6a21\u578b\u8868\u73b0\u53c2\u8003",
            "\u4e0d\u4ee3\u8868\u672a\u6765\u8d5b\u679c\u4fdd\u8bc1",
            "\u4e0d\u6784\u6210\u6295\u6ce8\u5efa\u8bae",
            "\u5728\u7ebf\u66f4\u65b0\u53ea\u8865\u8d5b\u679c\uff0c\u4e0d\u6539\u9884\u6d4b\u6a21\u578b",
            "\u4e0d\u662f\u5b9e\u65f6\u6bd4\u5206",
        ]:
            self.assertIn(text, js)
        for text in [
            "\u91cd\u65b0\u8bfb\u53d6\u672c\u673a\u4f53\u5f69\u6570\u636e",
            "\u672c\u6a21\u5f0f\u53ea\u8bfb\u53d6\u672c\u673a\u6570\u636e\u5e93",
            "\u672a\u914d\u7f6e\u6570\u636e\u5e93\u65f6\u4e0d\u4f1a\u8054\u7f51\u66f4\u65b0",
        ]:
            self.assertIn(text, lottery_js)

        risk_checked_js = js.replace("\u4e0d\u6784\u6210\u6295\u6ce8\u5efa\u8bae", "")
        risk_checked_html = html.replace("\u4e0d\u6784\u6210\u6295\u6ce8\u5efa\u8bae", "")
        for risky_word in [
            "\u7a33\u8d5a",
            "\u5fc5\u4e2d",
            "R" + "OI",
            "K" + "elly",
            "\u6700\u4f73\u6295\u6ce8",
            "\u4ef7\u503c\u6295\u6ce8",
            "\u6295\u6ce8\u5efa\u8bae",
            "\u4e0b\u6ce8",
            "\u5957\u5229",
            "\u6536\u76ca",
        ]:
            self.assertNotIn(risky_word, risk_checked_js)
            self.assertNotIn(risky_word, risk_checked_html)


if __name__ == "__main__":
    unittest.main()
