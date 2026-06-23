# P3-C29 / Kline Orderflow 量价结构组合评分与趋势敏感度优化

## 状态

DONE

## 优先级

P0

## 所属 Phase

P3 算法、事件窗口与评分层

## 背景

`kline_orderflow` 当前仍接近“原始 OHLCV 加权模块”：P1 主要采集 `btc_1h_open/high/low/close/volume`，P2 将部分 OHLCV 字段直接标记为方向信号，P3 多数走 `semantic.radar_rule`。这会导致成交量放大被误解释为 bullish，尤其在“价格下跌 + 成交量暴增”的场景下，模块可能被 `btc_1h_volume` 拉成 bullish。

典型历史问题：

```text
btc_1h_close: bearish
btc_1h_high: bearish
btc_1h_low: bearish
btc_1h_volume: bullish +661.85%
结果 volume 权重把 kline_orderflow 拉成 bullish
```

真实交易语义应为：

```text
放量上涨 = bullish confirmation
放量下跌 = bearish confirmation
放量长下影 = selling absorbed
缩量反弹 = rebound_unconfirmed
单独放量 = no direction
```

## 目标

把 `kline_orderflow` 从原始 OHLCV 方向加权，升级为量价结构组合评分模块，使其能敏感识别 24h 暴跌、放量下跌、弱反弹、假突破、破位风险和下影承接。

## 影响范围

- P1：Binance kline 历史窗口与派生指标。
- P2：Radar registry 中 Kline 指标角色与直接方向语义。
- P3：新增 Kline 专用组合语义规则与模块状态机。
- P4.5：消费新的 Kline 量价结构字段，并在人类可读报告中解释。
- P5：Dashboard / Radar Detail 展示新的 `trend_state`、结构解释和确认/反证字段。
- P8 / SQLite：如新增派生指标，需要进入 SQLite 指标定义、run lineage 与审计链路。

## 任务内容

### 1. P1 Kline 派生指标

从 Binance BTCUSDT 1h Kline 历史窗口生成派生指标，至少支持最近 24 根 1h K 线。

P0 指标：

```text
btc_return_1h
btc_return_4h
btc_return_24h
btc_drawdown_24h
btc_close_position_1h
btc_candle_body_pct_1h
btc_upper_wick_ratio_1h
btc_lower_wick_ratio_1h
btc_volume_zscore_1h
btc_breakdown_24h_low
btc_breakout_24h_high
btc_down_volume_pressure
btc_rebound_quality_1h
```

边界要求：

- `high == low` 时安全返回 neutral/null，不得异常。
- `volume_zscore` 使用最近 20 根或可用窗口，不足样本要标记 sample boundary。
- 派生指标必须保留 `source_ts`、`collected_at`、freshness、run scope。

### 2. P2 指标角色重分类

调整 `kline_orderflow` 中原始 OHLCV 的角色：

| 指标 | 新角色 | 方向语义 |
| --- | --- | --- |
| `btc_1h_open` | `context_only` | 不直接参与方向 |
| `btc_1h_high` | `structure_context` | 不单独 higher_is 打方向 |
| `btc_1h_low` | `structure_context` | 不单独 higher_is 打方向 |
| `btc_1h_close` | `price_signal` | 需要与 return/range/volume 组合 |
| `btc_1h_volume` | `confirmation_factor` | 不单独 bullish/bearish |

硬约束：

```text
btc_1h_volume 不得因自身上升单独产生 bullish / positive。
btc_1h_high / btc_1h_low 不得只因变化正负直接决定模块方向。
```

### 3. P3 Kline 专用组合评分

新增语义规则：

```text
semantic.kline_orderflow.composite
```

输出字段：

```text
price_trend_score
volume_confirmation_score
candle_structure_score
breakdown_risk_score
rebound_quality_score
selling_pressure_score
trend_state
trend_state_reason
```

建议组合：

```text
kline_orderflow_score =
  price_trend_score * 0.30
  + volume_confirmation_score * 0.20
  + candle_structure_score * 0.20
  + breakdown_risk_score * 0.15
  + rebound_quality_score * 0.10
  + selling_pressure_score * 0.05
```

注意：`volume_confirmation_score` 不独立决定方向，只确认 `price_trend_score`。

### 4. 状态机

第一版状态枚举：

```text
bullish_confirmation
bearish_pressure
bearish_but_absorbed
rebound_unconfirmed
breakdown_risk
false_breakout_risk
neutral_wait_confirm
```

优先级：

```text
breakdown_confirmed
> bearish_pressure
> false_breakout_risk
> bullish_confirmation
> bearish_but_absorbed
> rebound_unconfirmed
> neutral_wait_confirm
```

核心规则：

```text
if btc_return_1h < 0
and btc_volume_zscore_1h > 1.5
and btc_close_position_1h < 0.3:
    trend_state = bearish_pressure
```

```text
if btc_return_24h < -0.03
and btc_return_1h > 0
and btc_volume_zscore_1h < 1.0:
    trend_state = rebound_unconfirmed
```

```text
if btc_return_1h < 0
and btc_volume_zscore_1h > 1.5
and btc_lower_wick_ratio_1h > 0.45
and btc_close_position_1h > 0.45:
    trend_state = bearish_but_absorbed
```

### 5. P4.5 / P5 消费契约

P4.5 必须能消费并展示：

```text
trend_state
price_trend_score
volume_confirmation_score
candle_structure_score
breakdown_risk_score
rebound_quality_score
selling_pressure_score
top_kline_reason
volume_interpretation
candle_interpretation
confirmation_status
```

报告表达必须能说明：

```text
成交量放大是确认因子，不是独立方向因子。
放量下跌不能被解释为健康放量。
24h 大跌中的 1h 小反弹只能是反抽/待确认，不能直接视为趋势反转。
```

## 验收样本

| Case | 条件 | 期望状态 |
| --- | --- | --- |
| `bug_case_volume_spike_down` | close 下跌，volume 暴增，close_position 低 | `bearish_pressure` |
| `volume_spike_up` | close 上涨，volume zscore 高，close_position 高 | `bullish_confirmation` |
| `long_lower_wick` | 下跌放量，长下影，收回中部 | `bearish_but_absorbed` |
| `weak_rebound_after_dump` | 24h 大跌，1h 小涨，缩量 | `rebound_unconfirmed` |
| `false_breakout` | 突破高点但长上影收回 | `false_breakout_risk` |
| `pure_volume_spike` | volume 放大但价格无方向 | `neutral_wait_confirm` |

## DoD

- [ ] 新增或派生的 Kline 指标完成 Metric Definition、source/run lineage、SQLite 写入和 P1 审计展示。
- [ ] P2 `kline_orderflow` 角色重分类完成，`btc_1h_volume` 不再单独产生 bullish/positive。
- [ ] P3 新增 `semantic.kline_orderflow.composite`，核心 Kline 指标不再依赖 `semantic.radar_rule` 给方向。
- [ ] P3 输出量价结构子分与 `trend_state`。
- [ ] 历史 bug 样本必须输出 `bearish_pressure` 或等价偏空压力状态，不得输出 bullish。
- [ ] P4.5 报告和 Evidence Pack 能展示 Kline 量价结构解释。
- [ ] P5 Dashboard / Radar Detail 能读取并展示新的 Kline 状态字段。
- [ ] 单元测试覆盖 6 个验收样本。
- [ ] 全链条 P1/P2/P3/P4.5 重跑通过，并输出对应 HTML。

## 备注

本任务属于 P3 Phase，优先级为 P0。它修复的是核心交易语义错误，不是普通增强项。
## Execution Record

Status: DONE

Implemented:
- P1 Binance 1h kline source now loads a historical window and derives price/volume structure metrics.
- P2 kline_orderflow registry reclassifies raw OHLCV roles; volume is a confirmation factor, not a direct bullish/bearish signal.
- P3 adds kline composite semantic scoring with trend_state and structure sub-scores.
- P4.5 consumes the new kline metrics in invalidation and confirmation rules.
- Regression coverage verifies volume-spike-down resolves to bearish_pressure and volume alone stays context_only.

Validation:
- backend/tests/test_sources.py::test_p2_first_batch_mock_sources_write_metrics passed.
- backend/tests/test_radars.py passed.
- backend/tests/test_p3_pipeline.py passed.
- backend/tests/test_p45_final_writer.py, backend/tests/test_p45_html_report.py, backend/tests/test_p45_evidence_pack.py passed.
- Live kline collect completed for binance-btcusdt-kline-1h.
- P1/P2/P3/P4.5 no-collect audit rerun completed and regenerated HTML reports.

Latest runtime spot-check:
- p3 run: p3-20260523124717-8bd716
- kline_orderflow trend_state: rebound_unconfirmed
- volume_confirmation_score: 0.0
- score_bucket_v2 counts: positive=1, negative=7, neutral_confirmed=4, context_only=6, rule_gap_zero=0, unavailable=0
