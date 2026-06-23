# P3-C21 Scoring Rulebook 文档化与零分指标治理

## 状态

DONE - 文档与审计已完成，评分算法不在本任务内修改。后续规则优化进入 P3-C22。

## 所属 Phase

P3 算法、事件窗口与评分层

## 背景

P3-C16 到 P3-C20 已经建立了指标级评分、模块级评分、BTC 专业语义校准、freshness/horizon/duplicate 权重和 P4.5 Evidence 输入契约。

当前发现一个核心问题：P3 scored evidence 中仍有大量指标输出 `metric_score = 0`。其中一部分 0 分是合理的，例如上下文指标、未触发阈值、中性区间或不可直接推断 BTC 方向的指标；但也有一部分 0 分来自评分规则过保守、缺少阈值、缺少变化率语义或缺少组合规则。

如果大量主信号长期为 0，P4.5 会更容易输出“中性观察 / 方向共振不足”，即使底层数据已经出现趋势变化，也可能被评分层压平。

## 任务目标

建立一份可审计、可维护、可优化的 P3 Scoring Rulebook，并基于该文档识别长期 0 分指标的原因和治理优先级。

本任务只做文档化、审计统计和优化候选清单，不直接修改评分算法；评分规则调整放到 P3-C22。

## 本轮审计输入

审计文档：

```text
指标优化.md
```

生成脚本：

```text
scripts/generate_metric_optimization_doc.py
```

抽样 run：

```text
collect_run_id     = collect-20260523042729-6e54f8
p2_radar_run_id   = radar-20260523042917-2102c2
p3_run_id         = p3-20260523042918-0ffeb9
final_run_id      = p45final-20260523042921-e1797a
```

## 审计结果摘要

| 项目 | 结果 |
| --- | --- |
| 指标 evidence 数 | 118 |
| Radar module 数 | 14 |
| positive 指标 | 25 |
| negative 指标 | 25 |
| zero 指标 | 64 |
| unavailable 指标 | 4 |
| 零分占比 | 54.24% |
| 初步优化候选 | 58 |

结论：当前 P3 评分层已经具备结构化 scoring rulebook 基础，但零分占比仍然偏高。若不治理，高比例 zero bucket 会持续压低 P4.5 的趋势敏感度，使 final_view 更容易停留在 neutral/watch。

## 当前评分链路

```text
P1/P8 metric value
  -> P2 Radar module / metric role
  -> P3 semantic scoring rule
  -> metric_score
  -> freshness_weight
  -> horizon_weight
  -> duplicate_adjustment
  -> metric_effective_score
  -> module_score / module_effective_score
  -> P4.5 evidence pack
```

## 当前单指标评分规则

```text
base_metric_score = P2 Radar feature.score
base_direction    = P2 Radar feature.direction
metric_score      = semantic_override(metric_id, current, change, weight) 或 base_metric_score
score_bucket      = positive if metric_score > 0.0001
                  = negative if metric_score < -0.0001
                  = zero otherwise
unavailable       = available=false 或 feature_run_scope in {provider_required, missing}
```

## 当前有效分规则

```text
metric_effective_score =
  metric_score
  * quality_score
  * freshness_weight
  * horizon_weight
  * duplicate_adjustment
```

权重规则：

| 权重 | 当前规则 |
| --- | --- |
| freshness_weight | collection fresh=1.0, stale=0.65, expired=0.25；business current=1.0, expected_lag=0.95, lagging=0.85, outdated=0.65, unknown=0.9 |
| horizon_weight | h24=1.0, d3=0.9, d7=0.8, structural=0.7 |
| duplicate_adjustment | 同 duplicate_group_id 总绝对分超过 group cap 时按 cap/total 降权，最低 0.2 |

## 当前模块评分规则

```text
module_score = Σ metric_score
module_effective_score = Σ metric_effective_score

if unavailable_share >= 0.5 and abs(module_score) < 0.08:
    module_direction = unavailable
elif abs(module_score) < 0.08 and both positive/negative exist:
    module_direction = mixed
elif abs(module_score) < 0.08:
    module_direction = neutral
else:
    module_direction = bullish if module_score > 0 else bearish

module_effective_direction = sign(module_effective_score) with ±0.0001 threshold
module_strength = min(abs(module_score), 1.0)
```

## Semantic Rule 审计

| semantic_rule_id | 数量 | 审计判断 |
| --- | ---: | --- |
| semantic.radar_rule | 67 | 最大零分来源。多数指标沿用 P2 原始方向和 base_score，缺少 BTC 专业阈值、变化率或 regime 解释。 |
| semantic.context_only | 21 | 合理 0 分居多，但需要逐个确认是否有业务指标被误归类为上下文。 |
| semantic.unavailable | 4 | 不应视为中性，应在数据质量边界暴露。 |
| semantic.macro_surprise.zero_neutral | 2 | 当前 Forecast/Actual/Previous 未增强前，0 分合理。 |
| semantic.etf_flow.absolute_negative | 2 | ETF 净流出直接偏空，规则合理。 |
| semantic.funding.normalized | 2 | 温和区间只给轻微信号，建议与 OI 组合增强。 |
| semantic.oi.flat / semantic.oi.mild_change | 2+ | OI 轻微变化长期为 0，建议与 price/funding/volume 联动。 |
| MVRV / SOPR / NUPL / VIX / OFR / 利率 / PutCall / Basis / Options | 少量 | 已有明确阈值，0 分多数是落入中性区间或上下文区间。 |

## 零分原因分类

本轮 `zero=64`，主要分为：

| 零分原因 | 治理判断 |
| --- | --- |
| P2 方向中性/混合，或通用 radar_rule 分数接近 0 | 优先治理。需要为高价值主信号补专用阈值或变化率规则。 |
| context_only | 多数合理。需要确认是否误把主信号放入上下文。 |
| context_required | 优先治理。成本基础类指标需要与 BTC 现价组合。 |
| 落入中性阈值区间 | 多数合理。可以补斜率、连续天数或跨指标确认，不应强行打非 0。 |
| unavailable | 数据质量治理，不属于方向评分优化。 |

## 高优先级治理方向

1. `semantic.radar_rule` 且长期为 0 的 primary/core signal。
2. `context_required` 指标，例如 realized_price、cap_real_usd、STH/LTH cost basis，需要与 btc_price 相对位置组合。
3. OI / funding / price / volume 类微观结构指标，需要补联动规则，避免单项轻微变化长期为 0。
4. P4.5 文章经常引用但 P3 分数为 0 的指标，需要确认是否应该参与方向。
5. 影响 24h / 3d / 7d horizon 判断的指标，需要优先补足周期语义。

## 不建议直接改成非 0 的情况

以下 0 分不应机械优化：

```text
- 纯上下文指标
- 数据质量审计指标
- 未发布或未触发的事件指标
- SOPR 接近 1 的盈亏平衡区
- VIX 常态区间
- NUPL 温和盈利区
- Basis 接近零
- Macro surprise = 0 且没有 Forecast/Actual surprise
- provider unavailable 或 fallback 边界
```

这些指标可以继续保持 0 分，但必须在 P4.5 和前端解释为“中性/观察/上下文”，不能被误解为缺失。

## 产出文件

已生成：

```text
指标优化.md
```

文档已覆盖：

1. 全部 118 条 P3 scored evidence。
2. 14 个 Radar module。
3. 单指标评分公式。
4. 有效分公式。
5. 模块聚合公式。
6. Semantic Rulebook 摘要。
7. 零分原因分类。
8. 优先优化候选。
9. 每个指标的当前评分规则、0 分原因和优化优先级。

同时新增可复用生成脚本：

```text
scripts/generate_metric_optimization_doc.py
```

后续每次全链条跑完后，可以重新生成 `指标优化.md`，用于比较 zero_ratio、候选指标和模块方向变化。

## DoD 核对

| DoD | 状态 |
| --- | --- |
| Rulebook 覆盖全部 P3 scored evidence 指标 | PASS |
| 每个指标有当前评分规则或 context/unavailable 标记 | PASS |
| 每个 Radar module 有模块评分公式和方向规则 | PASS |
| 能列出 0 分指标及原因分类 | PASS |
| 能区分合理 0 分和需要优化的 0 分 | PASS |
| 为 P3-C22 提供高优先级优化清单 | PASS |
| 不改变现有 P4.5 契约字段 | PASS |
| 不修改评分算法 | PASS |

## 风险与注意事项

1. 本轮统计基于最新 live API 抽样，不代表历史长期分布；P3-C22 前建议再抽 3-5 次 run 做对比。
2. `semantic.radar_rule` 数量较多，不能一次性全部改，应按模块和主信号分批治理。
3. 0 分不是天然错误。错误的是“应该对 BTC 趋势敏感的指标长期没有方向贡献”。
4. P3-C22 修改评分规则后，必须全链条跑 P1/P2/P3/P4.5，观察 P4.5 final_view 是否变得过度敏感。

## 后续任务

进入 P3-C22：高优先级零分指标评分规则优化与阈值补全。

建议 P3-C22 第一批只处理：

```text
1. semantic.radar_rule 中 primary/core signal 长期 0 的指标
2. cost basis / realized price 与 btc_price 的组合规则
3. OI + funding + price + volume 联动规则
4. horizon 关键指标的 24h / 3d / 7d 趋势阈值
```

## 外部优化建议采纳评估

本轮补充建议的核心判断是正确的：当前问题不是指标数量不足，而是评分语义过粗、`semantic.radar_rule` 承担过多、模块聚合过于直接。P3-C21 采纳该方向，后续优先做评分语义与模块聚合治理，不先新增数据源。

### 采纳为 P3-C22 P0 范围

| 建议 | 采纳状态 | 落地说明 |
| --- | --- | --- |
| 指标分成 direction_signal / risk_signal / regime_signal / context_signal | 采纳 | 先作为 P3 metric role 扩展，不改变 P1/P2 原始数据。用于避免事件倒计时、风险指标被硬塞进 bullish/bearish。 |
| `event_policy` 改为 risk overlay | 采纳 | CPI/FOMC/NFP/PCE days_until 不直接给方向分，进入 event_risk_score、risk_lock、confidence_down。 |
| OI / Funding / Price / Volume 组合规则 | 采纳 | `btc_open_interest`、`btc_funding_rate` 不再孤立解释；优先在 derivatives_crowding / btc_total_state 中做组合评分。 |
| onchain cost basis 接 BTC price 相对位置 | 采纳 | realized_price、STH/LTH cost basis、cap_real_usd 从 context_required 升级为组合规则；cap_real_usd 本身不直接给方向，优先看 realized cap change。 |
| ETF Flow 保留绝对方向，同时增加压力缓和解释 | 采纳 | `flow_direction_score` 与 `flow_momentum_score` 分开，避免“净流出被写成偏多”的逻辑冲突。 |
| 模块聚合新增 coverage/conflict/confidence/top_contributors | 采纳 | P3 module output 增加聚合审计字段，为 P4.5 和前端提供更清晰的模块解释。 |
| raw direction 与 effective direction 冲突时显式标记 conflict | 采纳 | 例如 fund_flow raw bearish / effective bullish，应输出 conflict 或 bearish_but_improving，而不是简单取一边。 |

### 采纳但建议拆后续任务

| 建议 | 采纳状态 | 原因 |
| --- | --- | --- |
| 每个 Radar 输出 direction_score / risk_score / confidence_score / freshness_score | 采纳，拆分 | 属于模块契约升级，建议 P3-C23 单独做，避免 P3-C22 同时改太多结构。 |
| trend_state 状态机 | 采纳，拆分 | 对 P4.5 文章层价值很高，但需要先等模块 score/risk/conflict 稳定。建议 P3-C24 或 P4.5 后续任务接入。 |
| 新 Radar 权重表 | 部分采纳，拆分 | 权重会直接影响 final_view，需要先做 shadow calculation / 对照报告，再切主链路。 |
| macro_radar / asia_risk / options_volatility 专用规则 | 采纳，后置 | 作为 P1 优先级，在 fund_flow/event_policy/derivatives/onchain 四个 P0 模块之后处理。 |
| P4.5 发文状态映射 | 采纳，后置 | 需要等待 P3 输出 trend_state 或 module_state 后由 P4.5 消费。 |

### 暂不直接采纳

| 建议 | 原因 |
| --- | --- |
| 立即把 zero_ratio 从 54.24% 降到 35%-40% 作为硬 DoD | 可以作为目标，不作为硬门槛。部分 0 分是合理中性/上下文，强行降零分可能制造伪信号。 |
| 立即新增更多指标或数据源 | 暂不采纳。当前优先治理已有指标语义与模块聚合。 |
| 一次性重构全部 14 个模块 | 暂不采纳。应按 P0/P1/P2 分批，避免 final_view 方向漂移。 |

### 建议的新任务拆分

基于上述采纳评估，P3-C22 不应只做“补阈值”，而应改为第一批评分语义治理任务。建议后续任务顺序如下：

```text
P3-C22 高优先级零分指标评分规则优化与阈值补全
  - fund_flow: ETF 绝对方向 + momentum/pressure easing
  - event_policy: event_risk_score / risk_lock / confidence_down
  - derivatives_crowding: OI + Funding + Price 组合规则
  - onchain_valuation: BTC price vs realized/STH/LTH cost basis

P3-C23 Radar Module 聚合器升级
  - coverage_score
  - conflict_score
  - module_confidence
  - top_positive/top_negative/top_contributors
  - raw/effective direction conflict 标记

P3-C24 Radar 状态机与多维模块输出
  - direction_score
  - risk_score
  - confidence_score
  - freshness_score
  - trend_state: neutral_wait_confirm / bearish_but_improving / conflict_no_trade 等
```

### 对 P3-C22 的更新建议

P3-C22 的第一轮编码应优先覆盖以下模块：

| 优先级 | 模块 | 动作 |
| --- | --- | --- |
| P0 | fund_flow | 分离 ETF 绝对流向与流出收窄/扩大动量；冲突时输出 improving/conflict。 |
| P0 | event_policy | 事件倒计时改成 risk overlay，不参与方向硬打分。 |
| P0 | derivatives_crowding | Funding + OI + price 组合，输出 crowding/risk，而不是单指标方向。 |
| P0 | onchain_valuation | 接 BTC price 相对 realized/STH/LTH 成本基础。 |
| P1 | crypto_breadth | BTC.D、ETH/BTC、Fear&Greed 增加 regime 规则。 |
| P1 | macro_radar / treasury_credit | 静态阈值升级为 level + delta + curve。 |
| P1 | asia_risk | USDCNH、USDJPY、JGB、Nikkei/TOPIX 补风险规则。 |
| P1 | options_volatility | 增加 IV-RV spread、skew、expiry/window 解释。 |

## 关联任务

P3-C16, P3-C18, P3-C19, P3-C20, P3-C22, P4.5-C11, P4.5-C12
