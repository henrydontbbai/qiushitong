# 球势通 世界杯单场预测 MVP 方案

日期：2026-06-14  
当前范围：Phase 0 + Phase 1

## 目标

把 球势通 做成“本机绿色版世界杯预测助手”的最小闭环：用户双击启动后，点击“世界杯专题”，不配置数据库、不配置 AI Key，也能看到单场基础预测；配置 AI 后只用于白话解释。

## Phase 0：基线整理与风险清理

- 页面和说明文档统一使用“概率参考、模型模拟、理性娱乐、非决策建议”。
- 弱化或删除夸大承诺类表达。
- 保留本机免登录、前台设置、多厂商 AI 设置、绿色版打包能力。
- 不新增数据库表，不做在线同步，不做爬虫。

## Phase 1：世界杯单场预测 MVP

### 本地数据

数据放在 `data/worldcup/`：

- `teams.json`
- `fixtures_2026.json`
- `team_ratings.json`
- `data_sources.json`
- `model_versions.json`

每条数据记录来源说明、`source_id`、`data_cutoff_at`。本阶段只使用手动整理 JSON。

### 后端模块

预测逻辑必须放在 `scripts/worldcup/`：

- `data_loader.py`：读取本地 JSON。
- `team_aliases.py`：球队名称映射。
- `elo.py`：Elo 差值辅助。
- `goal_model.py`：简化 Poisson 比分分布。
- `odds.py`：赔率转市场隐含概率，仅做对照。
- `confidence.py`：数据完整度评分。
- `predictor.py`：单场预测入口。
- `explainer.py`：AI 或本地白话解释。

`app.py` 只保留薄 API：

- `GET /api/worldcup/fixtures`
- `POST /api/worldcup/predict`
- `POST /api/worldcup/explain`

### 前端闭环

- 导航栏增加“世界杯专题”。
- 页面展示赛程卡片。
- 点击比赛后展示胜/平/负概率、预期进球、Top 5 比分、数据完整度、模型版本、数据截止时间、风险提示。
- AI 按钮为“用 AI 翻译成白话分析”。
- AI 失败不影响基础预测结果。

## 明确暂缓

本轮不实现：

- 小组赛模拟
- 淘汰赛 / 冠军概率
- 预测快照
- 回测 / 校准
- 自动更新 / 爬虫 / 实时同步

## 验收标准

- 无数据库、无 AI Key 时，世界杯赛程和基础预测 API 可用。
- 胜/平/负概率合计约等于 1。
- Top 5 比分按概率降序。
- 赔率只作为市场隐含概率对照，不参与主模型。
- 页面明确显示“概率不代表赛果保证”。
- 源码和测试中不保留 Phase 3-5 的 backtest、snapshots、tournament 等实现。
