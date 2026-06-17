import os
import socket
import tempfile
import unittest
from pathlib import Path


class LauncherTest(unittest.TestCase):
    def test_find_free_port_skips_occupied_port(self):
        import launcher

        occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupied.bind(('127.0.0.1', 0))
        occupied.listen(1)
        used_port = occupied.getsockname()[1]
        try:
            free_port = launcher.find_free_port(used_port, used_port + 2)
        finally:
            occupied.close()

        self.assertNotEqual(free_port, used_port)
        self.assertIn(free_port, [used_port + 1, used_port + 2])

    def test_load_launcher_env_sets_local_defaults(self):
        import launcher

        keys = ['LOCAL_FREE_MODE', 'PORT', 'FLASK_DEBUG', 'QIUSHITONG_SETTINGS_PATH', 'MATCHPREDICT_SETTINGS_PATH']
        backup = {key: os.environ.get(key) for key in keys}
        for key in keys:
            os.environ.pop(key, None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                launcher.load_launcher_env(root, 8123)

                self.assertEqual(os.environ['LOCAL_FREE_MODE'], 'true')
                self.assertEqual(os.environ['PORT'], '8123')
                self.assertEqual(os.environ['FLASK_DEBUG'], 'false')
                self.assertEqual(os.environ['QIUSHITONG_SETTINGS_PATH'], str(root / 'settings.json'))
                self.assertNotIn('MATCHPREDICT_SETTINGS_PATH', os.environ)
        finally:
            for key, value in backup.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_wait_for_health_returns_false_for_unavailable_service(self):
        import launcher

        self.assertFalse(launcher.wait_for_health('http://127.0.0.1:1/health', timeout_seconds=1))

    def test_build_script_disables_upx_for_green_package_compatibility(self):
        script = Path('build_exe.ps1').read_text(encoding='utf-8')

        self.assertIn('--noupx', script)


    def test_build_script_uses_qiushitong_product_name(self):
        script = Path('build_exe.ps1').read_text(encoding='utf-8')

        self.assertIn('--name "QiuShiTong"', script)
        self.assertIn('dist\\QiuShiTong', script)
        self.assertIn('0x7403, 0x52BF, 0x901A', script)
        self.assertIn('0x7EFF, 0x8272, 0x7248', script)
        self.assertNotIn('--name "MatchPredict"', script)

    def test_launcher_uses_qiushitong_user_facing_name(self):
        launcher_source = Path('launcher.py').read_text(encoding='utf-8')

        self.assertIn("logging.getLogger('qiushitong.launcher')", launcher_source)
        self.assertIn('QiuShiTong launcher started', launcher_source)
        self.assertNotIn("logging.getLogger('matchpredict.launcher')", launcher_source)
        self.assertNotIn('MatchPredict launcher started', launcher_source)

    def test_build_script_excludes_setuptools_runtime_hook(self):
        script = Path('build_exe.ps1').read_text(encoding='utf-8')

        self.assertIn('--exclude-module "setuptools"', script)
        self.assertIn('--exclude-module "_distutils_hack"', script)


if __name__ == '__main__':
    unittest.main()
