# 球势通 本机世界杯概率分析工具

球势通 是一个本机绿色版足球概率分析工具。当前重点支持 **Phase 0 + Phase 1：2026 世界杯单场预测 MVP**。

> 所有输出都是模型概率参考，不代表赛果保证，不构成决策建议。AI 只负责把已有概率翻译成白话解释，不参与生成概率。

## 当前已支持

- 本机免登录、免费使用、无次数限制。
- Windows 绿色版可通过 `QiuShiTong.exe` 启动。
- 前台“设置”可填写数据库和多厂商 AI 接口。
- 世界杯专题使用本地 JSON 数据，无数据库、无 AI Key 也可用。
- 世界杯单场预测基于球队评分、Elo 差值和简化 Poisson 比分分布。
- 可选赔率只做“市场隐含概率对照”，不融合进主模型。

## 世界杯专题 MVP

用户点击“世界杯专题”后，可以选择赛程卡片并查看：

- 胜 / 平 / 负概率
- 双方预期进球
- Top 5 最可能比分
- 数据完整度
- 模型版本
- 数据截止时间
- 风险提示

配置 AI 后，可点击“用 AI 翻译成白话分析”。AI 解释不能改写概率，不能编造阵容、伤停、新闻。

## 本地世界杯数据

数据位于：

- `data/worldcup/teams.json`
- `data/worldcup/fixtures_2026.json`
- `data/worldcup/team_ratings.json`
- `data/worldcup/data_sources.json`
- `data/worldcup/model_versions.json`

每条数据需保留 `source_id`、来源说明和 `data_cutoff_at`。本阶段不做自动抓取。

## 小白使用

1. 解压绿色包。
2. 双击 `QiuShiTong.exe`。
3. 浏览器自动打开本地页面。
4. 点击“世界杯专题”，选择比赛查看基础预测。
5. 如果想看 AI 白话解释，再到右上角“设置”填写 AI 接口。

## 开发验证

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py launcher.py scripts\*.py scripts\worldcup\*.py
.\.venv\Scripts\python.exe -m unittest tests.test_worldcup_core tests.test_worldcup_api tests.test_worldcup_frontend_smoke
```

## 后续安排

后续能力会按独立安全包逐步开发，本轮只包含当前可试用版本。

## 风险说明

预测结果只是概率参考。足球比赛受阵容、临场状态、天气、红黄牌等因素影响，模型无法保证结果。
