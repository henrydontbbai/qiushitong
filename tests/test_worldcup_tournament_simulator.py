import unittest
from pathlib import Path

from scripts.worldcup.data_loader import WorldCupDataLoader
from scripts.worldcup.tournament_simulator import simulate_tournament


DATA_DIR = Path("data/worldcup")
ROUND_KEYS = [
    "round_of_32_probability",
    "round_of_16_probability",
    "quarter_final_probability",
    "semi_final_probability",
    "final_probability",
    "champion_probability",
]
EXPECTED_TOTALS = {
    "round_of_32_probability": 32.0,
    "round_of_16_probability": 16.0,
    "quarter_final_probability": 8.0,
    "semi_final_probability": 4.0,
    "final_probability": 2.0,
    "champion_probability": 1.0,
}


class WorldCupTournamentSimulatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = WorldCupDataLoader(DATA_DIR).load()

    def test_seeded_tournament_simulation_is_reproducible(self):
        first = simulate_tournament(self.data, DATA_DIR, trials=20, seed=2026)
        second = simulate_tournament(self.data, DATA_DIR, trials=20, seed=2026)

        self.assertEqual(first, second)
        self.assertTrue(first["success"])
        self.assertEqual(first["trials"], 20)
        self.assertEqual(len(first["teams"]), 48)
        self.assertIn("model_version", first)
        self.assertIn("data_cutoff_at", first)
        self.assertIn("概率参考，不代表赛果保证", first["disclaimer"])

    def test_round_probability_totals_and_bounds_are_valid(self):
        result = simulate_tournament(self.data, DATA_DIR, trials=30, seed=7)

        self.assertTrue(result["success"])
        for team in result["teams"]:
            for key in ROUND_KEYS:
                self.assertGreaterEqual(team[key], 0.0, key)
                self.assertLessEqual(team[key], 1.0, key)

        for key, expected in EXPECTED_TOTALS.items():
            self.assertAlmostEqual(result["round_totals"][key], expected, places=6, msg=key)

    def test_knockout_simulation_never_returns_draw_as_qualifier(self):
        result = simulate_tournament(self.data, DATA_DIR, trials=10, seed=99)
        text = str(result).lower()

        self.assertNotIn("'draw'", text)
        self.assertNotIn('"draw"', text)
        self.assertNotIn("平局晋级", str(result))


if __name__ == "__main__":
    unittest.main()
