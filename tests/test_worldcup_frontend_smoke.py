from pathlib import Path
import unittest


class WorldCupFrontendSmokeTest(unittest.TestCase):
    def test_worldcup_frontend_entry_and_script_are_present(self):
        html = Path("templates/index.html").read_text(encoding="utf-8")
        js = Path("static/js/worldcup.js").read_text(encoding="utf-8")

        self.assertIn("worldcup-mode-btn", html)
        self.assertIn("worldcup-mode-btn", html)
        self.assertIn("worldcup-mode", html)
        self.assertIn("js/worldcup.js", html)
        self.assertIn("v='phase-d1'", html)
        self.assertIn("worldcup-tournament-panel", html)
        self.assertIn("worldcup-meta-panel", html)
        self.assertIn("worldcup-groups-panel", html)
        self.assertIn("worldcup-bracket-panel", html)
        self.assertIn("worldcup-tournament-panel", html)
        self.assertNotIn("????", html)

        for text in [
            "renderProb",
            "Top 5",
            "renderDataQuality",
            "formatPercent",
            "formatXg",
            "/api/worldcup/meta",
            "/api/worldcup/groups?simulate=1",
            "/api/worldcup/bracket-rules",
            "/api/worldcup/tournament",
            "loadTournament",
            "renderTournament",
            "champion_probability",
            "round_of_16_probability",
            "event.target.closest('.worldcup-predict-btn')",
            "worldcup-tournament-table",
            "worldcup-tournament",
        ]:
            self.assertIn(text, js)

        for risky_word in [
            "\u7a33\u8d5a",
            "\u5fc5\u4e2d",
            "R" + "OI",
            "K" + "elly",
            "\u6700\u4f73\u6295\u6ce8",
            "\u4ef7\u503c\u6295\u6ce8",
            "\u4e0b\u6ce8",
            "\u5957\u5229",
            "\u6536\u76ca",
        ]:
            self.assertNotIn(risky_word, js)
            self.assertNotIn(risky_word, html)


if __name__ == "__main__":
    unittest.main()
