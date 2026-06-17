# 球势通 绿色 EXE 99 电脑冒烟验收记录（2026-06-15）

## 结论

通过。绿色包已发送到 **windows-99（192.168.0.99）桌面**并在 99 上完成冒烟验收。  
在不配置数据库、不配置 AI Key 的情况下，`QiuShiTong.exe` 可以启动本机服务，启动自检页、世界杯专题、单场基础预测、设置入口和导出入口均可用。

> 本次按要求不以本机 EXE 运行为验收结论；本机只做构建和自动化代码检查。

## 99 测试位置

- 目标设备：windows-99
- 远程测试目录：`C:\Users\Administrator\Desktop\QiuShiTong-green-smoke-nosetuptools-20260615-163630`
- 绿色包哈希（SHA256）：`AF0A04B1D5789334F46A6B132650B7BB930EDF947F1C4879CB8CAC4675537EA9`

## 本次修复

99 上旧绿色包会在 PyInstaller 启动早期卡住，且不会生成 `logs/launcher.log`。诊断包确认卡住点与 PyInstaller 打入的 `setuptools` 运行钩子相关。

最小修复：

- `build_exe.ps1`
  - 保留 `--noupx`，降低异机兼容风险。
  - 新增排除 `setuptools` / `_distutils_hack`，避免绿色包启动时执行不必要运行钩子。
- `tests/test_launcher.py`
  - 增加打包脚本保护测试，防止以后误删上述兼容参数。

## 99 上 EXE 启动验收

- `QiuShiTong.exe --check`：通过。
- `QiuShiTong.exe --no-browser`：服务启动成功。
- 默认启动 `QiuShiTong.exe`：日志显示已打开浏览器。
- 运行结束后已停止测试进程，99 上无残留 `球势通` 进程。

## 99 上 API 冒烟

- `/health`：服务可用。
- `/startup-check`：HTTP 200。
- `/api/worldcup/fixtures`：成功，返回 72 场赛程。
- `/api/worldcup/meta`：成功。
- `/api/worldcup/groups?simulate=1`：成功，返回 12 个小组。
- `/api/worldcup/predict`：成功。
- 胜 / 平 / 负概率合计：`1`。
- Top 比分：按概率降序。
- `/api/worldcup/explain`：成功；未配置 AI 时使用兜底解释，不影响基础预测。

## 99 上浏览器页面验收

使用 99 上的 Microsoft Edge 无界面模式读取 `http://127.0.0.1:8000/#worldcup-mode` 页面 DOM，确认页面包含：

- “世界杯专题”
- `settings-modal` 设置弹窗入口
- “概率不代表赛果保证” / 概率参考提示
- 复制、下载、打印导出入口

## 打包产物安全检查

99 解压目录检查未发现：

- `.env`
- `settings.json`
- `.pyc`
- `__pycache__`
- `.pytest_cache`
- `build/`

必要资源存在：

- `_internal/templates`
- `_internal/static`
- `_internal/data/worldcup`
- `_internal/scripts/worldcup`

## 本地自动检查

- `unittest discover`：41 个测试通过。
- Python 编译检查：通过。
- JS 语法检查：`static/js/settings.js`、`static/js/worldcup.js` 通过（使用 Node REPL 解析；本机 `node.exe` 被系统拒绝执行）。

## 未做内容

本次只做绿色 EXE 打包冒烟验收和最小打包兼容修复，未新增：

- 淘汰赛 / 冠军概率
- 回测 / 校准
- 预测快照
- 自动更新 / 爬虫
- 数据库结构变更
