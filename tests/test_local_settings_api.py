import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class LocalSettingsApiTest(unittest.TestCase):
    def setUp(self):
        os.environ['LOCAL_FREE_MODE'] = 'true'
        self.ai_env_keys = [
            'AI_PROVIDER',
            'AI_BASE_URL',
            'AI_API_KEY',
            'AI_MODEL',
            'GEMINI_API_KEY',
            'GEMINI_MODEL',
        ]
        self.ai_env_backup = {key: os.environ.get(key) for key in self.ai_env_keys}
        for key in self.ai_env_keys:
            os.environ.pop(key, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.settings_path = Path(self.tmp.name) / 'settings.json'
        self.app_module = importlib.import_module('app')
        self.app_module.app.config['TESTING'] = True
        self.path_patch = patch.object(self.app_module, 'LOCAL_SETTINGS_PATH', self.settings_path)
        self.path_patch.start()
        self.client = self.app_module.app.test_client()

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()
        for key, value in self.ai_env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_status_reports_unconfigured_without_leaking_secret_values(self):
        response = self.client.get('/api/local-settings/status')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertFalse(data['database_configured'])
        self.assertFalse(data['ai_configured'])
        self.assertIn('ai_provider', data)
        self.assertIn('ai_model', data)
        self.assertNotIn('db_password', data)
        self.assertNotIn('ai_api_key', data)

    def test_save_writes_openai_compatible_settings_and_status_masks_secrets(self):
        payload = {
            'database': {
                'host': 'localhost',
                'port': '5432',
                'name': 'postgres',
                'user': 'postgres',
                'password': 'secret-pass',
            },
            'ai': {
                'provider': 'openai_compatible',
                'base_url': 'https://api.openai.com/v1',
                'api_key': 'openai-secret-key',
                'model': 'gpt-test-model',
            }
        }

        response = self.client.post('/api/local-settings/save', json=payload)

        self.assertEqual(response.status_code, 200)
        saved = json.loads(self.settings_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['database']['password'], 'secret-pass')
        self.assertEqual(saved['ai']['provider'], 'openai_compatible')
        self.assertEqual(saved['ai']['base_url'], 'https://api.openai.com/v1')
        self.assertEqual(saved['ai']['api_key'], 'openai-secret-key')
        self.assertEqual(saved['ai']['model'], 'gpt-test-model')
        self.assertEqual(os.environ['DB_HOST'], 'localhost')
        self.assertEqual(os.environ['AI_PROVIDER'], 'openai_compatible')
        self.assertEqual(os.environ['AI_API_KEY'], 'openai-secret-key')

        status = self.client.get('/api/local-settings/status').get_json()
        self.assertTrue(status['database_configured'])
        self.assertTrue(status['ai_configured'])
        self.assertEqual(status['ai_provider'], 'openai_compatible')
        self.assertEqual(status['ai_model'], 'gpt-test-model')
        self.assertNotIn('secret-pass', json.dumps(status, ensure_ascii=False))
        self.assertNotIn('openai-secret-key', json.dumps(status, ensure_ascii=False))

    def test_legacy_gemini_settings_are_normalized_to_ai_settings(self):
        payload = {
            'gemini': {
                'api_key': 'gemini-secret-key',
                'model': 'gemini-2.5-flash-lite-preview-06-17',
            }
        }

        response = self.client.post('/api/local-settings/save', json=payload)

        self.assertEqual(response.status_code, 200)
        saved = json.loads(self.settings_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['ai']['provider'], 'gemini')
        self.assertEqual(saved['ai']['api_key'], 'gemini-secret-key')
        self.assertEqual(saved['ai']['model'], 'gemini-2.5-flash-lite-preview-06-17')

        status = self.client.get('/api/local-settings/status').get_json()
        self.assertTrue(status['ai_configured'])
        self.assertEqual(status['ai_provider'], 'gemini')
        self.assertEqual(status['ai_model'], 'gemini-2.5-flash-lite-preview-06-17')
        self.assertNotIn('gemini-secret-key', json.dumps(status, ensure_ascii=False))

    def test_index_has_settings_modal_before_settings_script(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('id="settings-btn"', html)
        self.assertNotIn('id="settings-btn" class="nav-btn" data-mode="settings"', html)
        self.assertLess(html.index('id="settings-modal"'), html.index('js/settings.js'))


    def test_test_db_uses_submitted_settings(self):
        payload = {
            'database': {
                'host': 'db.example.test',
                'port': '15432',
                'name': 'matchpredict',
                'user': 'mp_user',
                'password': 'mp_pass',
            }
        }

        with patch('app.psycopg2.connect') as connect:
            connect.return_value.close.return_value = None
            response = self.client.post('/api/local-settings/test-db', json=payload)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('数据库连接成功', data['message'])
        connect.assert_called_once()
        params = connect.call_args.kwargs
        self.assertEqual(params['host'], 'db.example.test')
        self.assertEqual(params['port'], 15432)
        self.assertEqual(params['database'], 'matchpredict')
        self.assertEqual(params['user'], 'mp_user')
        self.assertEqual(params['password'], 'mp_pass')

    def test_test_ai_uses_submitted_settings(self):
        payload = {
            'ai': {
                'provider': 'openai_compatible',
                'base_url': 'https://example.test/v1',
                'api_key': 'test-key',
                'model': 'test-model',
            }
        }

        class FakePredictor:
            init_args = None

            def __init__(self, **kwargs):
                FakePredictor.init_args = kwargs

            def test_connection(self):
                return True, 'AI 连接成功'

        with patch.object(self.app_module, 'AIFootballPredictor', FakePredictor):
            response = self.client.post('/api/local-settings/test-ai', json=payload)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('AI 连接成功', data['message'])
        self.assertEqual(FakePredictor.init_args['provider'], 'openai_compatible')
        self.assertEqual(FakePredictor.init_args['base_url'], 'https://example.test/v1')
        self.assertEqual(FakePredictor.init_args['api_key'], 'test-key')
        self.assertEqual(FakePredictor.init_args['model_name'], 'test-model')

    def test_ai_predict_uses_latest_settings_file(self):
        self.settings_path.write_text(json.dumps({
            'ai': {
                'provider': 'openai_compatible',
                'base_url': 'https://example.test/v1',
                'api_key': 'test-key',
                'model': 'test-model',
            }
        }), encoding='utf-8')

        class FakeAnalysis:
            match_id = 'm1'
            home_team = 'A'
            away_team = 'B'
            league_name = 'L'
            ai_analysis = '分析结果'
            home_odds = 2.1
            draw_odds = 3.2
            away_odds = 3.4

        class FakePredictor:
            init_args = None

            def __init__(self, **kwargs):
                FakePredictor.init_args = kwargs

            def analyze_matches(self, matches):
                return [FakeAnalysis()]

        with patch.object(self.app_module, 'AIFootballPredictor', FakePredictor):
            response = self.client.post('/api/ai/predict', json={
                'matches': [{
                    'match_id': 'm1',
                    'home_team': 'A',
                    'away_team': 'B',
                    'league_name': 'L',
                    'odds': {'hhad': {'h': 2.1, 'd': 3.2, 'a': 3.4}},
                }]
            })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['predictions'][0]['ai_analysis'], '分析结果')
        self.assertEqual(FakePredictor.init_args['provider'], 'openai_compatible')
        self.assertEqual(FakePredictor.init_args['base_url'], 'https://example.test/v1')
        self.assertEqual(FakePredictor.init_args['api_key'], 'test-key')
        self.assertEqual(FakePredictor.init_args['model_name'], 'test-model')


if __name__ == '__main__':
    unittest.main()
