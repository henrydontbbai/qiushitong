#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
球势通绿色版启动器。

双击 exe 后启动本机 Flask 服务，并自动打开浏览器。
"""

import argparse
import contextlib
import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen

from dotenv import load_dotenv


LOGGER = logging.getLogger('qiushitong.launcher')


def app_root() -> Path:
    """返回绿色包运行根目录。"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_free_port(start: int = 8000, end: int = 8020) -> int:
    """查找可用端口。"""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f'未找到可用端口，请关闭占用 {start}-{end} 的程序后重试。')


def load_launcher_env(root: Path, port: int) -> None:
    """读取绿色包旁边的设置文件，并设置基础环境变量。"""
    for filename in ('设置.env', '.env'):
        env_path = root / filename
        if env_path.exists():
            load_dotenv(env_path, override=True)

    os.environ['LOCAL_FREE_MODE'] = os.environ.get('LOCAL_FREE_MODE', 'true')
    os.environ['PORT'] = str(port)
    os.environ.setdefault('FLASK_DEBUG', 'false')
    os.environ.setdefault('QIUSHITONG_SETTINGS_PATH', str(root / 'settings.json'))




def build_launch_url(port: int) -> str:
    return f'http://127.0.0.1:{port}/startup-check'

def wait_for_health(url: str, timeout_seconds: int = 30) -> bool:
    """等待 Flask 服务可用。"""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                return response.status == 200
        except Exception:
            time.sleep(0.5)
    return False


def run_flask_app() -> None:
    """在当前进程内启动 Flask。"""
    import app

    port = int(os.environ['PORT'])
    app.app.run(debug=False, host='127.0.0.1', port=port, use_reloader=False)


class TeeStream:
    """同时写入控制台和日志文件。"""

    def __init__(self, console_stream, log_stream):
        self.console_stream = console_stream
        self.log_stream = log_stream
        self.encoding = getattr(console_stream, 'encoding', 'utf-8')

    def write(self, text):
        if isinstance(text, bytes):
            safe_text = text.decode('utf-8', errors='replace')
        else:
            safe_text = str(text)
        self.console_stream.write(safe_text)
        self.console_stream.flush()
        self.log_stream.write(safe_text)
        self.log_stream.flush()

    def flush(self):
        self.console_stream.flush()
        self.log_stream.flush()


def configure_logging(log_path: Path):
    """把正常启动过程和 Flask 日志写入 logs/launcher.log。"""
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().setLevel(logging.INFO)
    return file_handler


def main() -> int:
    parser = argparse.ArgumentParser(description='球势通绿色版启动器')
    parser.add_argument('--no-browser', action='store_true', help='只启动服务，不自动打开浏览器')
    parser.add_argument('--check', action='store_true', help='检查启动器配置后退出')
    args = parser.parse_args()

    root = app_root()
    logs_dir = root / 'logs'
    logs_dir.mkdir(exist_ok=True)
    log_path = logs_dir / 'launcher.log'
    file_handler = configure_logging(log_path)

    try:
        port = find_free_port(8000, 8020)
        load_launcher_env(root, port)

        with log_path.open('a', encoding='utf-8') as log_stream, \
                contextlib.redirect_stdout(TeeStream(sys.stdout, log_stream)), \
                contextlib.redirect_stderr(TeeStream(sys.stderr, log_stream)):
            print('球势通正在启动...')
            print(f'程序目录：{root}')
            print(f'访问地址：{build_launch_url(port)}')
            print('关闭此窗口即可停止服务。')
            LOGGER.info('QiuShiTong launcher started, root=%s, port=%s', root, port)

            if args.check:
                print('启动器检查通过。')
                LOGGER.info('Launcher check passed')
                return 0

            server_thread = threading.Thread(target=run_flask_app, daemon=True)
            server_thread.start()

            health_url = f'http://127.0.0.1:{port}/health'
            if not wait_for_health(health_url):
                raise RuntimeError('服务启动超时，请查看 logs/launcher.log')
            LOGGER.info('Health check passed: %s', health_url)

            if not args.no_browser:
                webbrowser.open(build_launch_url(port))
                LOGGER.info('Browser opened')

            while server_thread.is_alive():
                time.sleep(1)
            LOGGER.info('Flask server thread stopped')
            return 0

    except Exception as exc:
        message = f'启动失败：{exc}'
        print(message)
        LOGGER.exception('Launcher failed')
        with log_path.open('a', encoding='utf-8') as log_stream:
            log_stream.write(message + '\n')
        if sys.stdin and sys.stdin.isatty():
            input('按回车键退出...')
        return 1
    finally:
        logging.getLogger().removeHandler(file_handler)
        file_handler.close()


if __name__ == '__main__':
    raise SystemExit(main())
