import importlib
import os
import unittest
from unittest.mock import patch


class FakePredictionDB:
    def __init__(self):
        self.saved = []

    def save_classic_prediction(self, **kwargs):
        self.saved.append(('classic', kwargs))
        return True

    def save_ai_prediction(self, **kwargs):
        self.saved.append(('ai', kwargs))
        return True

    def save_lottery_prediction(self, **kwargs):
        self.saved.append(('lottery', kwargs))
        return True


class LocalFreeModeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['LOCAL_FREE_MODE'] = 'true'
        cls.app_module = importlib.import_module('app')
        cls.app_module.app.config['TESTING'] = True

    def setUp(self):
        self.fake_db = FakePredictionDB()
        self.db_patch = patch.object(self.app_module, 'prediction_db', self.fake_db)
        self.db_patch.start()
        self.client = self.app_module.app.test_client()

    def tearDown(self):
        self.db_patch.stop()

    def test_can_predict_without_login_in_local_free_mode(self):
        response = self.client.get('/api/user/can-predict')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['can_predict'])
        self.assertEqual(data['user_type'], 'local_free')
        self.assertEqual(data['remaining'], 'unlimited')

    def test_save_prediction_without_login_uses_anonymous_local_guest(self):
        response = self.client.post('/api/save-prediction', json={
            'mode': 'classic',
            'match_data': {
                'home_team': 'Arsenal FC',
                'away_team': 'Chelsea FC',
                'league_name': '英超',
                'home_odds': 2.1,
                'draw_odds': 3.2,
                'away_odds': 3.4,
            },
            'prediction_result': '主胜',
            'confidence': 8,
        })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(self.fake_db.saved[0][0], 'classic')
        self.assertIsNone(self.fake_db.saved[0][1]['user_id'])
        self.assertEqual(self.fake_db.saved[0][1]['username'], 'local_guest')

    def test_index_hides_auth_and_does_not_expose_gemini_key(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'secret-test-key'}, clear=False):
            response = self.client.get('/')

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('本机免费使用', html)
        self.assertNotIn('id="login-btn"', html)
        self.assertNotIn('id="register-btn"', html)
        self.assertNotIn('window.GEMINI_API_KEY', html)
        self.assertNotIn('secret-test-key', html)


if __name__ == '__main__':
    unittest.main()
