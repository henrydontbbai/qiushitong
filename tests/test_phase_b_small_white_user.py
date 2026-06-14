import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class PhaseBExperienceTest(unittest.TestCase):
    def setUp(self):
        os.environ['LOCAL_FREE_MODE'] = 'true'
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

    def test_startup_check_page_exists_and_shows_actions(self):
        response = self.client.get('/startup-check')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('启动自检', html)
        self.assertIn('进入世界杯专题', html)
        self.assertIn('打开设置', html)
        self.assertIn('logs/launcher.log', html)

    def test_launcher_opens_startup_check_url(self):
        import launcher
        self.assertEqual(launcher.build_launch_url(8123), 'http://127.0.0.1:8123/startup-check')

    def test_settings_modal_has_wizard_presets(self):
        html = Path('templates/index.html').read_text(encoding='utf-8')
        self.assertIn('只看世界杯基础预测', html)
        self.assertIn('我要 AI 白话解释', html)
        self.assertIn('我要体彩和保存记录', html)

    def test_worldcup_export_actions_present(self):
        js = Path('static/js/worldcup.js').read_text(encoding='utf-8')
        self.assertIn('复制当前结果', js)
        self.assertIn('下载 TXT', js)
        self.assertIn('打印', js)
        self.assertIn('copyCurrentPrediction', js)
        self.assertIn('downloadCurrentPredictionTxt', js)
        self.assertIn('printCurrentPrediction', js)


if __name__ == '__main__':
    unittest.main()
