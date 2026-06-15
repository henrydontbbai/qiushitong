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

        keys = ['LOCAL_FREE_MODE', 'PORT', 'FLASK_DEBUG', 'MATCHPREDICT_SETTINGS_PATH']
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
                self.assertEqual(os.environ['MATCHPREDICT_SETTINGS_PATH'], str(root / 'settings.json'))
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

    def test_build_script_excludes_setuptools_runtime_hook(self):
        script = Path('build_exe.ps1').read_text(encoding='utf-8')

        self.assertIn('--exclude-module "setuptools"', script)
        self.assertIn('--exclude-module "_distutils_hack"', script)


if __name__ == '__main__':
    unittest.main()
