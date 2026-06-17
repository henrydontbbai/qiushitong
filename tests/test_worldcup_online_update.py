import json
import tempfile
import unittest
from pathlib import Path


class WorldCupOnlineUpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime_dir = Path(self.tmp.name) / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = Path(self.tmp.name) / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        (self.data_dir / "teams.json").write_text(
            """{
  "teams": [
    {"team_id": "AUS", "display_name": "Australia", "display_name_zh": "澳大利亚", "aliases": ["Australia", "AUS"], "group": "D"},
    {"team_id": "TUR", "display_name": "Türkiye", "display_name_zh": "土耳其", "aliases": ["Türkiye", "Turkey", "TUR"], "group": "D"}
  ]
}
""",
            encoding="utf-8",
        )
        (self.data_dir / "fixtures_2026.json").write_text(
            """{
  "fixtures": [
    {
      "match_id": "WC2026-GD-007",
      "home_team_id": "AUS",
      "away_team_id": "TUR",
      "kickoff_at": "2026-06-14T03:00:00+08:00",
      "stage": "group",
      "group": "D",
      "venue": "BC Place Vancouver",
      "neutral_site": true,
      "status": "scheduled",
      "final_score": null,
      "source_id": "fixture-test"
    }
  ]
}
""",
            encoding="utf-8",
        )
        (self.data_dir / "team_ratings.json").write_text(
            """{
  "data_cutoff_at": "2026-06-11T00:00:00+08:00",
  "ratings": [
    {"team_id": "AUS", "elo": 1820, "fifa_rank": 24},
    {"team_id": "TUR", "elo": 1860, "fifa_rank": 19}
  ]
}
""",
            encoding="utf-8",
        )
        (self.data_dir / "data_sources.json").write_text(
            """{
  "sources": [{"source_id": "fixture-test", "name": "Test Fixture", "source_url": "https://example.com/base"}],
  "data_cutoff_at": "2026-06-14T00:00:00+08:00"
}
""",
            encoding="utf-8",
        )
        (self.data_dir / "model_versions.json").write_text(
            """{
  "active_model_version": "wc-elo-poisson-0.1.0",
  "models": [{"version": "wc-elo-poisson-0.1.0", "description": "Test model"}]
}
""",
            encoding="utf-8",
        )

        self.patch_payload = {
            "schema_version": 1,
            "source_id": "worldcup_results_patch_20260616",
            "source_url": "https://example.com/results_patch_latest.json",
            "published_at": "2026-06-16T09:00:00+08:00",
            "data_cutoff_at": "2026-06-16T09:00:00+08:00",
            "matches": [
                {
                    "match_id": "WC2026-GD-007",
                    "status": "finished",
                    "final_score": {"home": 2, "away": 0},
                    "data_cutoff_at": "2026-06-16T09:00:00+08:00"
                }
            ]
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_update_overrides_local_fixture_data(self):
        from scripts.worldcup.data_loader import WorldCupDataLoader
        from scripts.worldcup.online_update import apply_worldcup_update

        def fetcher(_url):
            return json.dumps(self.patch_payload)

        result = apply_worldcup_update(
            data_dir=self.data_dir,
            runtime_dir=self.runtime_dir,
            fetcher=fetcher,
            sources=[{"source_id": "test-source", "name": "Test", "url": "https://example.com/patch.json"}],
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["updated_matches_count"], 1)

        data = WorldCupDataLoader(self.data_dir, runtime_dir=self.runtime_dir).load()
        fixture = data.fixtures[0]
        self.assertEqual(fixture["status"], "finished")
        self.assertEqual(fixture["final_score"], {"home": 2, "away": 0})
        self.assertTrue(data.local_patch_applied)
        self.assertEqual(data.local_patch_matches_count, 1)
        self.assertEqual(data.base_data_cutoff_at, "2026-06-14T00:00:00+08:00")
        self.assertEqual(data.data_cutoff_at, "2026-06-16T09:00:00+08:00")

    def test_check_update_falls_back_to_second_source(self):
        from scripts.worldcup.online_update import check_worldcup_update

        calls = []

        def fetcher(url):
            calls.append(url)
            if "gitee" in url:
                raise RuntimeError("gitee unavailable")
            return json.dumps(self.patch_payload)

        result = check_worldcup_update(
            data_dir=self.data_dir,
            runtime_dir=self.runtime_dir,
            auto=False,
            fetcher=fetcher,
            sources=[
                {"source_id": "gitee_raw_primary", "name": "Gitee", "url": "https://gitee.example.com/patch.json"},
                {"source_id": "github_raw_fallback", "name": "GitHub", "url": "https://github.example.com/patch.json"}
            ],
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["update_available"])
        self.assertEqual(result["available_update"]["source_id"], "worldcup_results_patch_20260616")
        self.assertEqual(result["checked_source"]["source_id"], "github_raw_fallback")
        self.assertEqual(len(calls), 2)

    def test_invalid_patch_is_rejected_as_a_whole(self):
        from scripts.worldcup.online_update import apply_worldcup_update

        bad_patch = dict(self.patch_payload)
        bad_patch["matches"] = [
            {
                "match_id": "WC2026-GD-007",
                "status": "finished",
                "final_score": {"home": -1, "away": 0},
                "data_cutoff_at": "2026-06-16T09:00:00+08:00"
            }
        ]

        def fetcher(_url):
            return json.dumps(bad_patch)

        result = apply_worldcup_update(
            data_dir=self.data_dir,
            runtime_dir=self.runtime_dir,
            fetcher=fetcher,
            sources=[{"source_id": "test-source", "name": "Test", "url": "https://example.com/patch.json"}],
        )

        self.assertFalse(result["success"])
        self.assertIn("校验未通过", result["message"])
        self.assertIn("final_score", result["technical_detail"])
        patch_path = self.runtime_dir / "worldcup_overrides" / "results_patch_latest.json"
        self.assertFalse(patch_path.exists())

    def test_auto_check_obeys_cooldown_and_reuses_saved_state(self):
        from scripts.worldcup.online_update import check_worldcup_update

        calls = []

        def fetcher(_url):
            calls.append("called")
            return json.dumps(self.patch_payload)

        first = check_worldcup_update(
            data_dir=self.data_dir,
            runtime_dir=self.runtime_dir,
            auto=True,
            fetcher=fetcher,
            sources=[{"source_id": "test-source", "name": "Test", "url": "https://example.com/patch.json"}],
        )
        second = check_worldcup_update(
            data_dir=self.data_dir,
            runtime_dir=self.runtime_dir,
            auto=True,
            fetcher=fetcher,
            sources=[{"source_id": "test-source", "name": "Test", "url": "https://example.com/patch.json"}],
        )

        self.assertTrue(first["success"])
        self.assertEqual(len(calls), 1)
        self.assertTrue(second["success"])
        self.assertTrue(second["skipped_due_to_cooldown"])
        self.assertTrue(second["update_available"])

    def test_apply_update_rejects_older_patch_without_overwriting_local_patch(self):
        from scripts.worldcup.data_loader import WorldCupDataLoader
        from scripts.worldcup.online_update import apply_worldcup_update

        newer_patch = dict(self.patch_payload)
        older_patch = dict(self.patch_payload)
        older_patch["published_at"] = "2026-06-15T09:00:00+08:00"
        older_patch["data_cutoff_at"] = "2026-06-15T09:00:00+08:00"
        older_patch["matches"] = [
            {
                "match_id": "WC2026-GD-007",
                "status": "finished",
                "final_score": {"home": 1, "away": 0},
                "data_cutoff_at": "2026-06-15T09:00:00+08:00"
            }
        ]

        apply_worldcup_update(
            data_dir=self.data_dir,
            runtime_dir=self.runtime_dir,
            fetcher=lambda _url: json.dumps(newer_patch),
            sources=[{"source_id": "test-source", "name": "Test", "url": "https://example.com/newer.json"}],
        )

        result = apply_worldcup_update(
            data_dir=self.data_dir,
            runtime_dir=self.runtime_dir,
            fetcher=lambda _url: json.dumps(older_patch),
            sources=[{"source_id": "test-source", "name": "Test", "url": "https://example.com/older.json"}],
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "NO_NEWER_UPDATE")
        data = WorldCupDataLoader(self.data_dir, runtime_dir=self.runtime_dir).load()
        self.assertEqual(data.fixtures[0]["final_score"], {"home": 2, "away": 0})
        self.assertEqual(data.data_cutoff_at, "2026-06-16T09:00:00+08:00")

    def test_update_status_prefers_local_patch_applied_over_previous_check_failure(self):
        from scripts.worldcup.online_update import build_worldcup_update_status

        overrides_dir = self.runtime_dir / "worldcup_overrides"
        overrides_dir.mkdir(parents=True, exist_ok=True)
        (overrides_dir / "results_patch_latest.json").write_text(json.dumps(self.patch_payload), encoding="utf-8")
        (overrides_dir / "update_state.json").write_text(
            json.dumps(
                {
                    "last_checked_at": "2026-06-16T10:00:00+08:00",
                    "last_check_success": False,
                    "last_check_message": "temporary offline",
                    "checked_source": None,
                    "available_update": None,
                }
            ),
            encoding="utf-8",
        )

        status = build_worldcup_update_status(self.data_dir, self.runtime_dir)

        self.assertTrue(status["local_patch_applied"])
        self.assertEqual(status["local_patch_matches_count"], 1)
        self.assertEqual(status["display_status"], "本地补丁已应用")
        self.assertEqual(status["result_pending_count"], 0)

    def test_loader_ignores_corrupted_local_patch_file(self):
        from scripts.worldcup.data_loader import WorldCupDataLoader

        overrides_dir = self.runtime_dir / "worldcup_overrides"
        overrides_dir.mkdir(parents=True, exist_ok=True)
        (overrides_dir / "results_patch_latest.json").write_text("{bad json", encoding="utf-8")

        data = WorldCupDataLoader(self.data_dir, runtime_dir=self.runtime_dir).load()
        self.assertFalse(data.local_patch_applied)
        self.assertEqual(data.fixtures[0]["status"], "scheduled")
        self.assertEqual(data.data_cutoff_at, "2026-06-14T00:00:00+08:00")

    def test_empty_patch_is_not_treated_as_available_update(self):
        from scripts.worldcup.online_update import check_worldcup_update

        empty_patch = dict(self.patch_payload)
        empty_patch["matches"] = []

        result = check_worldcup_update(
            data_dir=self.data_dir,
            runtime_dir=self.runtime_dir,
            auto=False,
            fetcher=lambda _url: json.dumps(empty_patch),
            sources=[{"source_id": "test-source", "name": "Test", "url": "https://example.com/empty.json"}],
        )

        self.assertFalse(result["success"])
        self.assertFalse(result["update_available"])
        self.assertIn("还未发布", result["message"])
        self.assertIn("不包含可更新赛果", result["technical_detail"])

    def test_default_sources_include_gitee_primary_and_github_fallback(self):
        from scripts.worldcup.online_update import DEFAULT_WORLD_CUP_UPDATE_SOURCES

        self.assertEqual(DEFAULT_WORLD_CUP_UPDATE_SOURCES[0]["source_id"], "gitee_raw_primary")
        self.assertIn("gitee.com", DEFAULT_WORLD_CUP_UPDATE_SOURCES[0]["url"])
        self.assertIn("henrydontbbai/qiushitong", DEFAULT_WORLD_CUP_UPDATE_SOURCES[0]["url"])
        self.assertEqual(DEFAULT_WORLD_CUP_UPDATE_SOURCES[1]["source_id"], "github_raw_fallback")
        self.assertIn("raw.githubusercontent.com", DEFAULT_WORLD_CUP_UPDATE_SOURCES[1]["url"])
        self.assertIn("henrydontbbai/qiushitong", DEFAULT_WORLD_CUP_UPDATE_SOURCES[1]["url"])

    def test_env_override_sources_take_priority(self):
        import os
        from scripts.worldcup.online_update import DEFAULT_WORLD_CUP_UPDATE_SOURCES, _normalized_sources

        keys = [
            'QIUSHITONG_WORLDCUP_UPDATE_GITEE_URL',
            'QIUSHITONG_WORLDCUP_UPDATE_GITHUB_URL',
        ]
        backup = {key: os.environ.get(key) for key in keys}
        os.environ['QIUSHITONG_WORLDCUP_UPDATE_GITEE_URL'] = 'https://example.com/gitee.json'
        os.environ['QIUSHITONG_WORLDCUP_UPDATE_GITHUB_URL'] = 'https://example.com/github.json'
        try:
            sources = _normalized_sources(DEFAULT_WORLD_CUP_UPDATE_SOURCES)
        finally:
            for key, value in backup.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(sources[0]['url'], 'https://example.com/gitee.json')
        self.assertEqual(sources[1]['url'], 'https://example.com/github.json')
        self.assertNotIn('old.example.com', json.dumps(sources, ensure_ascii=False))

    def test_default_fetcher_falls_back_when_primary_strategy_fails(self):
        from unittest import mock
        from scripts.worldcup import online_update

        with mock.patch.object(online_update, "_fetch_via_requests", side_effect=RuntimeError("requests failed")), \
             mock.patch.object(online_update, "_fetch_via_urllib", return_value='{"ok":1}') as urllib_fetch:
            result = online_update.default_fetcher("https://example.com/patch.json")

        self.assertEqual(result, '{"ok":1}')
        urllib_fetch.assert_called_once()

    def test_fallback_fetchers_use_consistent_user_agent(self):
        from unittest import mock
        from scripts.worldcup import online_update

        completed = mock.Mock(returncode=0, stdout='{}', stderr='')
        with mock.patch.object(online_update.subprocess, "run", return_value=completed) as run:
            self.assertEqual(online_update._fetch_via_powershell("https://example.com/patch.json"), '{}')
            powershell_command = " ".join(run.call_args.args[0])
            self.assertIn("QiuShiTong/1.0", powershell_command)

        with mock.patch.object(online_update.subprocess, "run", return_value=completed) as run:
            self.assertEqual(online_update._fetch_via_curl("https://example.com/patch.json"), '{}')
            curl_command = run.call_args.args[0]
            self.assertIn("QiuShiTong/1.0", curl_command)



if __name__ == "__main__":
    unittest.main()
