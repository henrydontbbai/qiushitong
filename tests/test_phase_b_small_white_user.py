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
        self.assertIn('\u542f\u52a8\u81ea\u68c0', html)
        self.assertIn('\u8fdb\u5165\u4e16\u754c\u676f\u4e13\u9898', html)
        self.assertIn('\u6253\u5f00\u8bbe\u7f6e', html)
        self.assertIn('logs/launcher.log', html)

    def test_launcher_opens_startup_check_url(self):
        import launcher
        self.assertEqual(launcher.build_launch_url(8123), 'http://127.0.0.1:8123/startup-check')

    def test_settings_modal_has_wizard_presets(self):
        html = Path('templates/index.html').read_text(encoding='utf-8')
        self.assertIn('\u53ea\u770b\u4e16\u754c\u676f\u57fa\u7840\u9884\u6d4b', html)
        self.assertIn('\u6211\u8981 AI \u767d\u8bdd\u89e3\u91ca', html)
        self.assertIn('\u6211\u8981\u4f53\u5f69\u548c\u4fdd\u5b58\u8bb0\u5f55', html)

    def test_worldcup_export_actions_present(self):
        html = Path('templates/index.html').read_text(encoding='utf-8')
        js = Path('static/js/worldcup.js').read_text(encoding='utf-8')
        self.assertIn('\u590d\u5236\u5f53\u524d\u7ed3\u679c', html)
        self.assertIn('\u4e0b\u8f7d TXT', html)
        self.assertIn('\u6253\u5370', html)
        self.assertIn('\u5df2\u590d\u5236\u5f53\u524d\u7ed3\u679c', js)
        self.assertIn('copyCurrentPrediction', js)
        self.assertIn('downloadCurrentPredictionTxt', js)
        self.assertIn('printCurrentPrediction', js)

    def test_worldcup_hash_mode_is_supported(self):
        startup_html = Path('templates/startup_check.html').read_text(encoding='utf-8')
        nav_js = Path('static/js/nav-fix.js').read_text(encoding='utf-8')

        self.assertIn('#worldcup-mode', startup_html)
        self.assertIn('applyModeFromHash', nav_js)
        self.assertIn("'worldcup'", nav_js)
        self.assertIn('hashchange', nav_js)
        self.assertIn('replace(/-mode$/', nav_js)

    def test_worldcup_manager_initializes_after_dom_ready(self):
        js = Path('static/js/worldcup.js').read_text(encoding='utf-8')

        self.assertIn('function initWorldCupManager()', js)
        self.assertIn("document.readyState === 'loading'", js)
        self.assertIn('initWorldCupManager();', js)

    def test_worldcup_copy_has_fallback(self):
        js = Path('static/js/worldcup.js').read_text(encoding='utf-8')

        self.assertIn('copyTextWithFallback', js)
        self.assertIn('document.execCommand', js)
        self.assertIn('\u5df2\u590d\u5236\u5f53\u524d\u7ed3\u679c', js)
        self.assertIn('\u590d\u5236\u5931\u8d25', js)


if __name__ == '__main__':
    unittest.main()
