# GitHub 足球 / 世界杯 / 体育赛事概率参考项目调研归档

归档日期：2026-06-14  
项目：MatchPredict  
调研目的：为“世界杯赛程概率参考”寻找可借鉴的足球建模、赛制模拟、回测校准和 AI 解释层实现。

> 说明：本次调研为只读公开检索。GitHub 连接器令牌当时已过期，因此使用公开 GitHub API / README 页面辅助检索。未修改远程仓库、配置或凭据。  
> 风险边界：本文只归档概率模型、赛制模拟、赔率数学和回测校准方面的工程参考。MatchPredict 不提供资金决策建议，也不指导相关决策。

---

## 一、总论

GitHub 上存在不少相关项目。对 MatchPredict 最有参考价值的方向，不是让 AI 直接猜赛果，而是以下透明概率体系：

```text
Elo / 球队强度评分
+ Poisson / Dixon-Coles 进球模型
+ Monte Carlo 全赛程模拟
+ Walk-forward 回测
+ 概率校准
+ 市场隐含概率对照
+ LLM 白话解释层
```

推荐产品路线：

1. 用透明统计模型输出概率参考；
2. 用 Monte Carlo 模拟小组赛、淘汰赛和赛事路径；
3. 用赔率只做市场隐含概率 baseline 和对照，不直接当作答案；
4. 用 LLM 解释模型结论，而不是单独生成概率或赛果结论。

---

## 二、优先参考项目

| 优先级 | 项目 | 方向 | 可借鉴点 |
|---|---|---|---|
| S | [Hicruben/world-cup-2026-prediction-model](https://github.com/Hicruben/world-cup-2026-prediction-model) | 2026 世界杯概率模型 | Elo + Dixon-Coles + Monte Carlo，贴近世界杯赛制路径模拟 |
| S | [martineastwood/penaltyblog](https://github.com/martineastwood/penaltyblog) | 足球建模工具库 | Poisson、Dixon-Coles、Elo、市场隐含概率，可作为模型工具箱参考 |
| S | [georgedouzas/sports-betting](https://github.com/georgedouzas/sports-betting) | 通用体育概率建模 / 回测 | 数据加载、概率模型、市场概率比较、回测管线 |
| A | [hjjbh1314/worldcup-predictor](https://github.com/hjjbh1314/worldcup-predictor) | 世界杯 Elo / ML 回测 | 无数据泄漏、赛前可知特征、RPS / Brier / log-loss 验证思路 |
| A | [lbenz730/world_cup_2026](https://github.com/lbenz730/world_cup_2026) | 世界杯贝叶斯模拟 | Bayesian bivariate Poisson + Monte Carlo，严谨但迁移成本较高 |
| A | [0xNadr/wc2026](https://github.com/0xNadr/wc2026) | 世界杯全赛制模拟 | 晋级路径、赛事路径概率、比分分布，产品形态完整 |
| B | [kochlisGit/ProphitBet-Soccer-Bets-Predictor](https://github.com/kochlisGit/ProphitBet-Soccer-Bets-Predictor) | 足球 ML 概率应用 | 数据下载 → 特征 → 训练 → 概率输出 → 保存的完整流程 |
| B | [msoczi/football_predictions](https://github.com/msoczi/football_predictions) | 五大联赛 XGBoost | 三分类概率、特征工程、规则化后处理 |
| B | [sedemmler/WagerBrain](https://github.com/sedemmler/WagerBrain) | 赔率数学工具 | 去水位、隐含概率、风险指标计算 |
| B | [FabianWunderlichSpoho/BettingOddsPerformanceAnalysis](https://github.com/FabianWunderlichSpoho/BettingOddsPerformanceAnalysis) | 足球赔率分析 | 从赔率反推市场概率 / 预期进球，可做 baseline |

---

## 三、重点项目摘要

### 1. Hicruben / world-cup-2026-prediction-model

- URL：https://github.com/Hicruben/world-cup-2026-prediction-model
- 类型：2026 FIFA World Cup 赛果路径概率参考。
- 方法：Elo + Dixon-Coles 双变量 Poisson + Monte Carlo。
- 验证：walk-forward 回测，RPS、log-loss、Brier、ECE 等指标。
- 数据：国际比赛历史结果、实时赛果、2026 世界杯赛制 / 晋级规则。
- 可借鉴：世界杯赛制模拟、小组赛 / 淘汰赛条件更新、已结束比赛锁定、单场概率和比分分布输出。
- 风险：项目较新，需要检查数据完整性、实现质量，以及 live 逻辑是否完整开放。

### 2. martineastwood / penaltyblog

- URL：https://github.com/martineastwood/penaltyblog
- 类型：足球建模工具库。
- 方法：Poisson、Bivariate Poisson、Dixon-Coles、Bayesian、Elo、Massey、Colley、Pi ratings、市场隐含概率等。
- 数据：StatsBomb、Opta、Understat、Club Elo、FPL、赔率数据等接口 / 抓取。
- 可借鉴：作为 MatchPredict 的足球概率模型工具箱。
- 风险：它是库，不是完整世界杯预测产品；仍需自建数据管线和赛制模拟。

### 3. georgedouzas / sports-betting

- URL：https://github.com/georgedouzas/sports-betting
- 类型：通用体育概率建模工具，示例偏足球。
- 方法：Python；dataloader + bettor 架构；scikit-learn；CLI / GUI；时间序列交叉验证、回测、市场概率对照。
- 数据：历史赛果、fixtures、赔率，支持 market maximum odds。
- 可借鉴：数据加载 → 概率模型 → 市场概率比较 → 回测 → 差异分析输出。
- 风险：偏通用框架，不等于世界杯模型本身；世界杯特征、赛制模拟、校准评估需要另做。

### 4. hjjbh1314 / worldcup-predictor

- URL：https://github.com/hjjbh1314/worldcup-predictor
- 类型：世界杯概率建模 / 回测项目。
- 方法：Elo、ML、赛前可知特征、概率校准。
- 可借鉴：避免数据泄漏、按时间切分训练验证、用 RPS / Brier / log-loss 评估概率。
- 风险：需要确认数据质量、样本量和赛制适配。

### 5. lbenz730 / world_cup_2026

- URL：https://github.com/lbenz730/world_cup_2026
- 类型：2026 世界杯贝叶斯模拟。
- 方法：Bayesian bivariate Poisson + Monte Carlo。
- 可借鉴：更严谨的进球模型和不确定性表达。
- 风险：迁移成本高，本地绿色版第一阶段不适合直接引入复杂依赖。

### 6. 0xNadr / wc2026

- URL：https://github.com/0xNadr/wc2026
- 类型：2026 世界杯全赛制模拟产品。
- 方法：比赛概率、比分分布、赛程路径模拟、前端展示。
- 可借鉴：页面信息结构、赛事路径展示、模拟结果解释。
- 风险：需要核对 2026 赛制规则和第三名晋级分配规则。

### 7. kochlisGit / ProphitBet-Soccer-Bets-Predictor

- URL：https://github.com/kochlisGit/ProphitBet-Soccer-Bets-Predictor
- 类型：机器学习足球概率应用。
- 方法：Neural Networks、Random Forests、Ensemble models、交叉验证、Holdout、可解释模型。
- 可借鉴：数据下载、特征工程、模型训练、概率输出和结果保存流程。
- 风险：偏俱乐部联赛；国家队 / 世界杯赛制适配成本较高。

### 8. WagerBrain

- URL：https://github.com/sedemmler/WagerBrain
- 类型：赔率数学工具包。
- 方法：赔率转换、隐含概率、去水位、风险指标、Elo 概率。
- 可借鉴：赔率标准化、市场隐含概率、风险指标处理。
- 风险：不是完整预测框架；需要自行实现数据质量、回测和概率校准。

---

## 四、对 MatchPredict 的落地建议

### 1. 保持“AI 解释层”，不要让 AI 直接给概率

- AI 适合做：把已有概率、xG、比分分布翻译成白话。
- AI 不适合做：脱离模型直接生成胜平负概率或赛果结论。
- 解释层必须明确：概率不代表赛果保证。

### 2. 先做透明单场模型，再做赛制模拟

推荐顺序：

1. 单场 Elo + Poisson；
2. 小组积分榜；
3. 小组赛 Monte Carlo；
4. 淘汰赛路径模拟；
5. 回测与校准；
6. Dixon-Coles 或更复杂模型。

### 3. 市场概率只做对照

- 赔率可以转换成市场隐含概率，用于对照模型输出。
- 第一版不把市场概率融合进主模型。
- 页面文案避免任何资金决策导向。

### 4. 回测和校准要晚于 MVP

- 回测必须避免赛后数据泄漏。
- 指标建议：Brier Score、Log Loss、RPS、ECE。
- 若模型过度自信，再考虑温度缩放或其他校准方法。

---

## 五、下一阶段推荐路线

### P0：当前已完成的基础方向

- 本机免登录。
- 前台设置 AI / 数据库。
- 世界杯单场预测 MVP。
- AI 只做解释。
- 基础风险文案清理。

### P1：优先增强

- 数据版本面板。
- 当前小组积分榜。
- 小组赛模拟。
- 端到端浏览器验收。

### P2：谨慎增强

- 淘汰赛路径模拟。
- 赛事路径概率。
- 回测与校准。
- Dixon-Coles 模型验证。

### P3：暂缓

- 自动抓取 FIFA / 赔率 / 伤停数据。
- 实时同步。
- 复杂球员级模型。
- 金靴等衍生玩法。

---

## 六、结论

MatchPredict 的合理路线是：

```text
透明概率模型
+ 本地数据版本说明
+ 小组赛 / 淘汰赛赛制模拟
+ 回测校准
+ AI 白话解释
```

第一阶段应继续保持“无配置可用、AI 只解释、概率不承诺结果”的定位。市场赔率和外部项目只作为工程参考，不作为产品决策建议。
