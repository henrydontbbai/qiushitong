from pathlib import Path
import unittest


class WorldCupGroupSimulatorTest(unittest.TestCase):
    def test_group_simulation_returns_2026_group_qualification_probabilities(self):
        from scripts.worldcup.data_loader import WorldCupDataLoader
        from scripts.worldcup.group_simulator import simulate_group_stage

        data = WorldCupDataLoader(Path("data/worldcup")).load()
        result = simulate_group_stage(data, trials=40, seed=2026)

        self.assertTrue(result["success"])
        self.assertEqual(result["trials"], 40)
        self.assertEqual(len(result["groups"]), 12)
        teams = [team for group in result["groups"] for team in group["teams"]]
        self.assertEqual(len(teams), 48)

        group_first_total = sum(team["group_first_probability"] for team in teams)
        top_two_total = sum(team["top_two_probability"] for team in teams)
        third_qualify_total = sum(team["third_qualify_probability"] for team in teams)
        qualify_total = sum(team["qualify_probability"] for team in teams)

        self.assertAlmostEqual(group_first_total, 12.0, places=6)
        self.assertAlmostEqual(top_two_total, 24.0, places=6)
        self.assertAlmostEqual(third_qualify_total, 8.0, places=6)
        self.assertAlmostEqual(qualify_total, 32.0, places=6)
        for team in teams:
            for key in [
                "group_first_probability",
                "top_two_probability",
                "third_qualify_probability",
                "qualify_probability",
            ]:
                self.assertGreaterEqual(team[key], 0.0)
                self.assertLessEqual(team[key], 1.0)


if __name__ == "__main__":
    unittest.main()
