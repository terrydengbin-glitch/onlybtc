# P3-C45 / Macro Radar v3 状态机与二段式评分

## 状态

DONE

## 目标

新增 `p3.c45.macro_radar.v3` profile，将 `macro_radar` 升级为 BTC 4h-3d 趋势的宏观确认、反证与冲击风险识别模块。

## 模块结构

```text
macro_radar.v3
= equity_beta
+ rates_pressure
+ dollar_pressure
+ volatility_stress
+ financial_stress
+ commodity_context
+ macro_impulse
+ btc_relative_confirmation
+ event_window
```

## 输出契约

```json
{
  "module": "macro_radar",
  "version": "p3.c45.macro_radar.v3",
  "module_purpose": "btc_macro_trend_confirmation_and_refutation",
  "equity_beta": {},
  "rates_pressure": {},
  "dollar_pressure": {},
  "volatility_stress": {},
  "financial_stress": {},
  "commodity_context": {},
  "macro_impulse": {},
  "btc_relative_confirmation": {},
  "event_window": {},
  "macro_trend_state": "macro_trend_confirmed_bullish|macro_tailwind_but_btc_lagging|macro_headwind_confirmed_bearish|btc_resisting_macro_headwind|macro_shock_risk|macro_mixed|macro_neutral",
  "module_direction": "bullish|bearish|neutral",
  "module_score": 0,
  "risk_score": 0,
  "confidence_adjustment": 0,
  "btc_implication": "macro_confirmed_uptrend|macro_confirmed_downtrend|macro_tailwind_not_absorbed|btc_internal_strength_against_macro|wait_for_confirmation|neutral",
  "support_drivers": [],
  "pressure_drivers": [],
  "risk_drivers": [],
  "invalidation_conditions": [],
  "context_notes": []
}
```

## 状态机

必须覆盖：

```text
macro_trend_confirmed_bullish
macro_tailwind_but_btc_lagging
macro_headwind_confirmed_bearish
btc_resisting_macro_headwind
macro_shock_risk
macro_mixed
macro_neutral
```

## 评分

```text
macro_environment_score =
  0.24 * equity_beta_score
+ 0.22 * rates_pressure_score
+ 0.18 * dollar_pressure_score
+ 0.16 * volatility_stress_score
+ 0.10 * financial_stress_score
+ 0.10 * commodity_context_score

module_score =
  macro_environment_score
+ 0.30 * macro_impulse_score
+ 0.25 * btc_relative_confirmation_score
- penalty_score

module_score = clamp(module_score, -0.50, +0.50)
```

## 业务约束

- 宏观顺风但 BTC 不跟随时，不允许强行输出强 bullish。
- 宏观逆风但 BTC residual 为正时，不允许直接压成强 bearish。
- VIX / OFR / macro shock 更偏风险和交易许可，不应单独定义价格方向。
- 高冲击事件窗口内，`macro_impulse` 权重提高，但强方向需要 BTC relative confirmation。

## DoD

- 输出完整 v3 结构。
- DXY、VIX、Nasdaq、Gold、Oil 不再单独产生 bullish/bearish driver。
- 能区分宏观顺风 BTC 跟随、宏观顺风 BTC 滞后、宏观逆风 BTC 跟跌、宏观逆风 BTC 抗跌、宏观冲击风险。
- `risk_score` 与 `module_score` 分离。
- 测试覆盖所有状态机核心场景。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
.\.venv\Scripts\python.exe -m compileall -q backend/src/onlybtc
```
