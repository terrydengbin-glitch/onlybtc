# P3-C33 Top Contributors 使用语义方向而非分数方向

## 状态

DONE

## 背景

P3-C32 已经把 `derivatives_crowding` 的 Funding/OI 语义修正为：

- Funding mild：`direction=neutral`
- `direction_contribution=mild_support`
- OI flat：`direction=neutral`
- 模块：`module_effective_direction=neutral`
- 模块状态：`crowding_state=not_crowded`、`trend_state=neutral_wait_confirm`

但最新审计发现 `top_contributors` 仍会把正分贡献项显示为：

```text
btc_funding_rate direction = bullish
```

这不是底层指标语义错误，而是贡献列表展示层把“正分贡献方向”误当成“指标语义方向”。这会误导 Dashboard、P3 HTML、P4.5 摘要和人工审计。

## 目标

修复 `top_contributors` 的方向语义：

1. `top_contributors.direction` 必须优先使用 metric item 的真实 `direction`。
2. 新增 `contribution_side = positive|negative|zero` 表达它对分数的贡献方向。
3. 新增/透传 `direction_contribution`，用于表达 `mild_support`、`mild_pressure`、`neutral` 等边际贡献。
4. Funding mild 这类风险信号应显示为：

```json
{
  "metric_id": "btc_funding_rate",
  "direction": "neutral",
  "contribution_side": "positive",
  "direction_contribution": "mild_support"
}
```

而不是：

```json
{
  "metric_id": "btc_funding_rate",
  "direction": "bullish"
}
```

## 不改范围

- 不修改实际 `metric_score`。
- 不修改 `metric_effective_score`。
- 不修改 `score_bucket` 计算。
- 不修改 P3-C32 的 Funding/OI 组合规则。
- 不修改 P4.5 总聚合权重。

## 修改点

### P3

`_module_contributor_item` / `_module_top_contributors`：

- `direction` 使用 `item["direction"]`。
- 新增 `contribution_side`：

```text
metric_effective_score > 0 => positive
metric_effective_score < 0 => negative
else => zero
```

- 透传：

```text
direction_contribution
funding_state
crowding_signal
trend_confirmation
oi_state
oi_confirmation
oi_trend_signal
```

### P3 HTML / P4.5 API

不需要额外重算，只要读取新的 `top_contributors` 字段即可。

## 验收样例

输入：

```json
{
  "metric_id": "btc_funding_rate",
  "direction": "neutral",
  "metric_effective_score": 0.0549,
  "direction_contribution": "mild_support"
}
```

期望 `top_contributors`：

```json
{
  "metric_id": "btc_funding_rate",
  "direction": "neutral",
  "contribution_side": "positive",
  "direction_contribution": "mild_support"
}
```

## DoD

- [x] `top_contributors.direction` 不再由正负分重新推导。
- [x] `btc_funding_rate direction=neutral` 时，贡献列表不得显示 `bullish`。
- [x] 正负贡献改由 `contribution_side` 表达。
- [x] Dashboard / Radar Detail / P3 HTML 不再把 mild funding support 误展示为趋势 bullish。
- [x] 新增回归测试覆盖 Funding mild + OI flat。
- [x] P3 / P45 相关测试通过。

## 实施记录

- `_module_contributor_item()` 的 `direction` 改为优先使用指标语义方向 `item["direction"]`。
- 新增 `contribution_side` 表达贡献方向，避免把正分误读成趋势偏多。
- `top_contributors` 透传 `direction_contribution`、`funding_state`、`crowding_signal`、`trend_confirmation`、`oi_state`、`oi_confirmation`、`oi_trend_signal`。
- P3-C32 回归样例扩展断言：Funding mild + OI flat 的贡献项应为 `direction=neutral`、`contribution_side=positive`、`direction_contribution=mild_support`。

## 测试

- `.venv\Scripts\python.exe -m pytest backend/tests/test_p3_pipeline.py::test_derivatives_crowding_funding_mild_oi_flat_is_not_bullish -q`
- `.venv\Scripts\python.exe -m pytest backend/tests/test_p3_pipeline.py -q`
- `.venv\Scripts\python.exe -m pytest backend/tests/test_p45_dashboard_api.py backend/tests/test_p45_explanations.py -q`

## 关联

P3-C32, P5-C38, P4.5-C21
