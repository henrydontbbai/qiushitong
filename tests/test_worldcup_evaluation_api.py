import os
import unittest


class WorldCupEvaluationApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['LOCAL_FREE_MODE'] = 'true'
        import app as app_module
        cls.app_module = app_module

    def setUp(self):
        self.client = self.app_module.app.test_client()

    def test_evaluation_report_endpoint_works_without_database_or_ai_key(self):
        response = self.client.get('/api/worldcup/evaluation/report')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['available'])
        self.assertIn('metrics', data)
        self.assertIn('calibration', data)
        self.assertIn('概率参考', data['disclaimer'])
        self.assertNotIn('api_key', response.get_data(as_text=True).lower())


if __name__ == '__main__':
    unittest.main()
