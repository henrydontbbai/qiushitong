import json
from pathlib import Path
import unittest


class WorldCupResultsPatchManifestTest(unittest.TestCase):
    def test_results_patch_manifest_has_safe_schema(self):
        from scripts.worldcup.online_update import _validate_patch_payload

        patch_path = Path("data/worldcup/results_patch_latest.json")
        payload = json.loads(patch_path.read_text(encoding="utf-8"))

        self.assertEqual(payload.get("schema_version"), 1)
        self.assertIsInstance(payload.get("matches"), list)
        self.assertIn("source_id", payload)
        self.assertIn("source_url", payload)
        self.assertIn("published_at", payload)
        self.assertIn("data_cutoff_at", payload)
        self.assertGreaterEqual(len(payload.get("matches", [])), 1)
        _validate_patch_payload(payload, Path("data/worldcup"))


if __name__ == "__main__":
    unittest.main()
