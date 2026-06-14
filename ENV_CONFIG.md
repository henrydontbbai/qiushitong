# MatchPredict 本机配置说明

本机绿色版优先通过前台“设置”保存配置到程序目录的 `settings.json`。普通用户不需要手动编辑 `.env`。

## 数据库配置（可选）

经典模式和世界杯专题不依赖数据库。体彩模式、保存记录需要 PostgreSQL：

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASS`

## AI 配置（可选）

AI 只用于解释已有预测结果，不参与世界杯概率计算。支持：

- OpenAI 兼容接口：填写 Base URL、API Key、模型名。
- Gemini：填写 Gemini Key 和模型名。

请不要把 API Key 提交到 GitHub。`settings.json`、`.env`、日志和打包目录都应保持忽略。

## 本机启动

```powershell
.\.venv\Scripts\python.exe app.py
```

默认访问：`http://127.0.0.1:8000`

## 风险文案原则

页面和说明统一使用“概率参考、模型模拟、理性娱乐、非决策建议”。不得出现夸大收益或结果保证类表达。
