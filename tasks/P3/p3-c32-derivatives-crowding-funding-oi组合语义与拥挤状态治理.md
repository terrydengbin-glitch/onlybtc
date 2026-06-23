# P3-C32 Derivatives Crowding Funding-OI 组合语义与拥挤状态治理

## 状态

DONE

## 背景

最新一轮 `derivatives_crowding` 审计结果：

- `module_score = 0.06`
- `module_effective_score = 0.0549`
- `module_direction = neutral`
- `module_effective_direction = bullish`
- `trend_state = neutral_wait_confirm`
- `module_state = balanced`
- `risk_score = 17.5`
- `confidence_score = 98.6`

核心指标：

- `btc_funding_rate = 0.00006462`，`metric_score = +0.06`
- `btc_open_interest = 102629.84`，`metric_score = 0`

业务含义应为：

> Funding 温和，OI flat，衍生品没有明显过热，但也没有确认趋势。当前更准确的表达是“拥挤风险低 / 等待确认 / 轻微边际支撑”，而不是直接 `bullish`。

当前计算没有大错，但输出语义偏粗：`module_effective_direction = bullish` 和 `btc_funding_rate direction = bullish` 容易让前端和文章层误读成“衍生品看多”。

## 目标

把 `derivatives_crowding` 从“方向判断模块”升级为“杠杆拥挤状态模块”。

1. Funding 温和为正，不直接显示强趋势 bullish。
2. OI flat 时，不允许 Funding 单独把模块打成 bullish。
3. `module_effective_score` 很小的时候，输出 `mild_support` 或 `neutral`，不输出 `bullish`。
4. 区分趋势方向、拥挤风险、边际支撑。
5. P4.5 / Dashboard / 文章层优先使用 `crowding_state`、`leverage_heat_state`、`module_effective_bias`，而不是直接使用 funding direction。

## 不改范围

- 不修改 P1 数据采集。
- 不修改 Funding / OI 原始值。
- 不强行加入新数据源。
- 不删除现有 `risk_score` / `confidence_score`。
- 不把 `derivatives_crowding` 改成趋势主导模块。

## Schema 增量

在 `derivatives_crowding` 模块输出中增加：

```json
{
  "trend_direction": "bullish|bearish|neutral",
  "trend_state": "confirmed_bullish|confirmed_bearish|neutral_wait_confirm|mixed",
  "crowding_state": "not_crowded|balanced|long_crowded|short_crowded|overheated|squeeze_risk",
  "leverage_heat_state": "low|low_to_normal|normal|elevated|hot|extreme",
  "module_effective_bias": "mild_support|mild_pressure|neutral|strong_support|strong_pressure",
  "confirmation_state": "confirmed|unconfirmed|conflicting"
}
```

Funding 指标增加：

```json
{
  "funding_state": "funding_negative|funding_mild|funding_elevated|funding_hot|funding_extreme",
  "crowding_signal": "not_hot|long_crowding|short_crowding|neutral",
  "direction_contribution": "mild_support|mild_pressure|neutral",
  "trend_confirmation": "confirmed|unconfirmed"
}
```

OI 指标增加：

```json
{
  "oi_state": "oi_rising|oi_falling|oi_flat",
  "oi_confirmation": "confirms_trend|confirms_crowding|none",
  "oi_trend_signal": "bullish_confirmed|bearish_confirmed|unconfirmed"
}
```

## 规则

### Effective Direction Deadband

```text
if abs(module_effective_score) < 0.10:
    module_effective_direction = neutral
    module_effective_bias = mild_support / mild_pressure / neutral

elif 0.10 <= module_effective_score < 0.25:
    module_effective_direction = mild_bullish
    module_effective_bias = mild_support

elif module_effective_score >= 0.25:
    module_effective_direction = bullish
    module_effective_bias = strong_support

elif -0.25 < module_effective_score <= -0.10:
    module_effective_direction = mild_bearish
    module_effective_bias = mild_pressure

else:
    module_effective_direction = bearish
    module_effective_bias = strong_pressure
```

### Funding + OI 组合规则

```text
if funding_state == funding_mild and oi_state == oi_flat:
    trend_direction = neutral
    trend_state = neutral_wait_confirm
    crowding_state = not_crowded
    leverage_heat_state = low_to_normal
    module_effective_bias = mild_support
    confirmation_state = unconfirmed
```

### Funding 高位规则

```text
if funding_state in ["funding_hot", "funding_extreme"] and oi_state == "oi_rising":
    crowding_state = long_crowded
    leverage_heat_state = hot
    trend_direction = neutral
    module_effective_bias = mild_pressure
```

### 负 Funding + OI 上升

```text
if funding_state == "funding_negative" and oi_state == "oi_rising":
    crowding_state = short_crowded
    leverage_heat_state = elevated
    module_effective_bias = mild_support
    confirmation_state = unconfirmed
```

## P4.5 / 文章层表达

禁止表达：

```text
Funding 为正，衍生品看多。
```

推荐表达：

```text
Funding 处于温和水平，OI 变化不大，说明杠杆资金没有明显追涨，当前衍生品端更像“拥挤风险低、等待确认”，不能作为强多信号。
```

短版：

```text
衍生品风险不高，但趋势确认不足：Funding 温和，OI flat，说明杠杆端没有明显过热，也没有形成强方向推动。
```

## 验收样例

输入：

```json
{
  "btc_funding_rate": 0.00006462,
  "btc_open_interest": 102629.84,
  "oi_change_state": "flat",
  "module_score": 0.06,
  "module_effective_score": 0.0549
}
```

期望输出：

```json
{
  "module_direction": "neutral",
  "module_effective_direction": "neutral",
  "module_effective_bias": "mild_support",
  "trend_state": "neutral_wait_confirm",
  "module_state": "balanced",
  "trend_direction": "neutral",
  "crowding_state": "not_crowded",
  "leverage_heat_state": "low_to_normal",
  "confirmation_state": "unconfirmed",
  "indicators": {
    "btc_funding_rate": {
      "funding_state": "funding_mild",
      "crowding_signal": "not_hot",
      "direction_contribution": "mild_support",
      "trend_confirmation": "unconfirmed"
    },
    "btc_open_interest": {
      "oi_state": "oi_flat",
      "oi_confirmation": "none",
      "oi_trend_signal": "unconfirmed"
    }
  }
}
```

## DoD

- [x] Funding 温和为正时，单项不得直接输出 strong bullish。
- [x] Funding mild + OI flat 时，模块不得输出 bullish。
- [x] `module_effective_score < 0.10` 时，`module_effective_direction` 必须为 `neutral`。
- [x] `risk_score` 低只能表达 crowding risk low，不能表达 trend bullish。
- [x] `confidence_score` 只表达数据可信度，不能表达方向置信度。
- [x] P4.5 文章层必须能输出“拥挤风险低 / 等待确认”。
- [x] 回归样例通过。

## 实施记录

- P3 `derivatives_crowding` 增加专属 effective direction deadband：`abs(module_effective_score) < 0.10` 输出 `neutral`。
- Funding 指标增加 `funding_state`、`crowding_signal`、`direction_contribution`、`trend_confirmation`。
- OI 指标增加 `oi_state`、`oi_confirmation`、`oi_trend_signal`。
- Funding mild + OI flat 输出 `crowding_state=not_crowded`、`leverage_heat_state=low_to_normal`、`confirmation_state=unconfirmed`。
- 新增回归测试 `test_derivatives_crowding_funding_mild_oi_flat_is_not_bullish`。

## 测试

- `.venv\Scripts\python.exe -m pytest backend/tests/test_p3_pipeline.py::test_derivatives_crowding_funding_mild_oi_flat_is_not_bullish backend/tests/test_p3_pipeline.py::test_scored_evidence_applies_p3_c22_high_priority_rules -q`
- `.venv\Scripts\python.exe -m pytest backend/tests/test_p3_pipeline.py::test_kline_orderflow_volume_spike_down_is_bearish_pressure -q`
- `.venv\Scripts\python.exe -m pytest backend/tests/test_p3_pipeline.py -q`
- `.venv\Scripts\python.exe -m pytest backend/tests/test_p45_dashboard_api.py backend/tests/test_p45_explanations.py -q`

## 关联

P3-C21, P3-C22, P3-C23, P3-C24, P3-C27, P4.5-C11, P4.5-C12, P5-C39
