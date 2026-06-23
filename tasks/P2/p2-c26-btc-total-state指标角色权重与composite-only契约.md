# P2-C26 / BTC Total State 指标角色、权重与 composite-only 契约

## 状态
DONE

## 背景

P3-C41 要求 `btc_total_state` 分成短线方向、合约确认、周期背景和审计上下文。P2 Registry 需要先明确各指标的角色、权重和 driver eligibility，避免 P3/P4.5/UI 把 raw price、OI、Funding、Halving、Block Height 混成同一种方向信号。

## 目标

调整 `btc_total_state` 的指标契约：

```text
price_state:
  btc_price
  btc_1h_close

perp_state:
  btc_funding_rate
  btc_open_interest

cycle_context:
  btc_halving_estimated_days
  btc_halving_blocks_remaining

audit_context:
  btc_block_height
```

## 契约要求

```text
btc_price / btc_1h_close:
  role = price_state
  composite-only
  不单独解释为 bullish / bearish driver

btc_funding_rate / btc_open_interest:
  role = perp_state
  composite-only
  不单独解释为 bullish / bearish driver

btc_halving_estimated_days / btc_halving_blocks_remaining:
  role = cycle_context
  weight = 0
  affects_signal = false
  affects_confidence = false

btc_block_height:
  role = audit_context
  weight = 0
  affects_signal = false
  affects_confidence = false
```

如新增 `driver_eligible` 字段，则 composite/context/audit 指标设置：

```text
driver_eligible = false
```

## DoD

- Registry 支持 `price_state`、`perp_state`、`cycle_context`、`audit_context` 角色。
- Halving 与 block height 不再进入方向评分。
- Funding / OI 在 `btc_total_state` 中只作为组合输入，不单独进入 support/pressure drivers。
- 与 `derivatives_crowding` 的 Funding/OI duplicate group 保持一致，避免重复放大。
- P2/P3 contract tests 通过。

## Execution Notes

- `RadarMetricRule` 新增 `driver_eligible` 契约字段。
- `MetricRole` 增加 `price_state`、`perp_state`、`cycle_context` 等角色。
- `btc_total_state` 中：
  - `btc_price` / `btc_1h_close` 改为 `price_state` composite-only。
  - `btc_funding_rate` / `btc_open_interest` 改为 `perp_state` composite-only。
  - `btc_halving_estimated_days` / `btc_halving_blocks_remaining` 改为 `cycle_context`。
  - `btc_block_height` 保持 `audit_context`。
- 上述指标均不再由 P2 通用 radar rule 单独贡献方向分。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radars.py -q
```

结果：`9 passed`。
