import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts.worldcup.evaluation import EvaluationError, evaluate_matches, load_evaluation_report
from scripts.worldcup.metrics import brier_score, expected_calibration_error, log_loss, ranked_probability_score


class WorldCupMetricsTest(unittest.TestCase):
    def test_brier_log_loss_and_rps_are_reproducible(self):
        probabilities = {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}
        self.assertAlmostEqual(brier_score(probabilities, "home_win"), 0.38, places=6)
        self.assertAlmostEqual(log_loss(probabilities, "home_win"), -math.log(0.5), places=6)
        self.assertAlmostEqual(ranked_probability_score(probabilities, "home_win"), 0.145, places=6)

    def test_ece_uses_confidence_buckets(self):
        samples = [
            {"probabilities": {"home_win": 0.60, "draw": 0.25, "away_win": 0.15}, "actual_result": "home_win"},
            {"probabilities": {"home_win": 0.70, "draw": 0.20, "away_win": 0.10}, "actual_result": "away_win"},
        ]
        report = expected_calibration_error(samples, bucket_count=5)
        self.assertEqual(report["bucket_count"], 5)
        self.assertGreaterEqual(report["ece"], 0)
        self.assertEqual(report["sample_count"], 2)


class WorldCupEvaluationTest(unittest.TestCase):
    def _write_payload(self, tmp: Path, matches):
        path = tmp / "evaluation_matches.json"
        path.write_text(json.dumps({"matches": matches}, ensure_ascii=False), encoding="utf-8")
        return path

    def test_evaluate_matches_skips_unfinished_and_scores_finished_samples(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            payload = [
                {
                    "match_id": "m1",
                    "kickoff_at": "2026-06-10T10:00:00+00:00",
                    "predicted_at": "2026-06-09T10:00:00+00:00",
                    "data_cutoff_at": "2026-06-09T00:00:00+00:00",
                    "probabilities": {"home_win": 0.55, "draw": 0.25, "away_win": 0.20},
                    "actual_result": "home_win",
                },
                {
                    "match_id": "m2",
                    "kickoff_at": "2026-06-11T10:00:00+00:00",
                    "predicted_at": "2026-06-10T10:00:00+00:00",
                    "data_cutoff_at": "2026-06-10T00:00:00+00:00",
                    "probabilities": {"home_win": 0.40, "draw": 0.30, "away_win": 0.30},
                    "actual_result": None,
                },
            ]
            report = evaluate_matches(self._write_payload(tmp, payload))
            self.assertEqual(report["sample_count"], 1)
            self.assertEqual(report["skipped_count"], 1)
            self.assertIn("brier_score", report["metrics"])
            self.assertIn("概率参考", report["disclaimer"])

    def test_evaluate_matches_rejects_post_match_prediction_leakage(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            payload = [{
                "match_id": "leak1",
                "kickoff_at": "2026-06-10T10:00:00+00:00",
                "predicted_at": "2026-06-10T10:01:00+00:00",
                "data_cutoff_at": "2026-06-09T00:00:00+00:00",
                "probabilities": {"home_win": 0.55, "draw": 0.25, "away_win": 0.20},
                "actual_result": "home_win",
            }]
            with self.assertRaises(EvaluationError):
                evaluate_matches(self._write_payload(tmp, payload))

    def test_evaluate_matches_rejects_post_match_data_cutoff_leakage(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            payload = [{
                "match_id": "leak2",
                "kickoff_at": "2026-06-10T10:00:00+00:00",
                "predicted_at": "2026-06-09T10:00:00+00:00",
                "data_cutoff_at": "2026-06-10T10:01:00+00:00",
                "probabilities": {"home_win": 0.55, "draw": 0.25, "away_win": 0.20},
                "actual_result": "home_win",
            }]
            with self.assertRaises(EvaluationError):
                evaluate_matches(self._write_payload(tmp, payload))

    def test_load_evaluation_report_returns_fallback_without_report(self):
        with tempfile.TemporaryDirectory() as td:
            report = load_evaluation_report(Path(td))
            self.assertFalse(report["available"])
            self.assertIn("暂无", report["message"])


if __name__ == "__main__":
    unittest.main()
