# P3-C38 / Trade Structure Price Response 确认层评分接入

## 状态

DONE

## 背景

P3-C37 的核心规则要求：

```text
taker_buy_sell_ratio 强，不等于趋势确认。
必须结合 price_response_state 判断主动买卖盘是否被价格接受。
```

P1-C42 会新增 5m / 15m price response 派生指标。本任务负责在 P3 评分层消费这些字段。

## 目标

在 `trade_structure_flow` 中新增 `price_response_state` 与 `flow_price_efficiency` 评分逻辑，使主动成交压力必须经过价格响应确认。

## 输入字段

优先使用：

```text
btc_return_5m
btc_return_15m
btc_close_position_5m
btc_close_position_15m
btc_range_expansion_z_5m
btc_volume_zscore_5m
btc_flow_price_efficiency_5m
```

fallback 使用：

```text
btc_return_1h
btc_close_position_1h
btc_volume_zscore_1h
btc_candle_body_pct_1h
```

## 状态规则

```text
taker_buy_sell_ratio > 1.30
and btc_return_5m > 0
and btc_return_15m > 0
and btc_close_position_5m > 0.55
  -> price_response_state = upside_response
  -> trade_structure_state 可进入 bullish_confirmation

taker_buy_sell_ratio > 1.30
and btc_return_5m <= 0
  -> price_response_state = no_upside_response
  -> trade_structure_state = absorption_or_trapped_long

taker_buy_sell_ratio > 1.30
and btc_return_5m > 0
and btc_close_position_5m < 0.45
  -> price_response_state = upside_rejected
  -> trade_structure_state = buy_pressure_rejected

taker_buy_sell_ratio < 0.70
and btc_return_5m >= 0
  -> price_response_state = no_downside_response
  -> trade_structure_state = sell_absorption_or_trapped_short
```

## 输出字段

```json
{
  "price_response_state": "upside_response|downside_response|no_upside_response|no_downside_response|upside_rejected|downside_rejected|unknown",
  "price_response_confidence": 0.0,
  "flow_price_efficiency_state": "efficient|inefficient|neutral|unknown",
  "price_response_source": "5m_15m|1h_fallback"
}
```

## 不改范围

- 不新增 P1 数据源，本任务只消费 P1-C42 产物。
- 不覆盖 P3-C37 的总体状态机，只补充价格响应确认层。
- 不让 5m 噪音单独决定最终方向。

## DoD

- P3 优先使用 5m / 15m price response 字段。
- 5m / 15m 缺失时 fallback 到 1h，并标记 `price_response_source=1h_fallback`。
- `taker_buy_sell_ratio > 1.30` 但 price response 未确认时，不得输出 `bullish_confirmation`。
- P3 Evidence 中能看到 price response 解释。
- P4.5 / P9 / P5 可以透传并展示 `price_response_state`。
- 单元测试覆盖 upside_response、no_upside_response、upside_rejected、sell_absorption 四类样本。

## 验收样本

```json
{
  "taker_buy_sell_ratio": 1.35,
  "btc_return_5m": -0.001,
  "btc_close_position_5m": 0.38
}
```

期望：

```json
{
  "price_response_state": "no_upside_response",
  "trade_structure_state": "absorption_or_trapped_long",
  "confirmation_state": "unconfirmed"
}
```

## Execution Notes

- P3 指标级 Evidence 已消费 P1-C42 的 5m / 15m price response 指标。
- 新增 price response confirmation semantic：
  - `price_response_state`
  - `price_response_confidence`
  - `flow_price_efficiency_state`
  - `price_response_source`
- `price_response_source` 优先输出 `5m_15m`，短周期缺失时 fallback 到 `1h_fallback`。
- price response 指标保持 `metric_score=0.0`，作为确认层上下文，不让 5m 噪音单独决定最终方向。
- P3-C37 模块状态机已改用 C38 状态枚举：
  - `upside_response`
  - `no_upside_response`
  - `upside_rejected`
  - `downside_response`
  - `no_downside_response`
  - `downside_rejected`
  - `unknown`
- `taker_buy_sell_ratio > 1.30` 但 `btc_return_5m <= 0` 时输出：
  - `price_response_state=no_upside_response`
  - `trade_structure_state=absorption_or_trapped_long`
  - `confirmation_state=unconfirmed`

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
```

结果：`27 passed`。
