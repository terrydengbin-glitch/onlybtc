# P2-C30 / Macro Radar v3 role、composite-only 与 risk-context registry

## 状态

DONE

## 目标

将 `macro_radar` registry 从单指标方向加权，升级为角色型 composite profile 输入契约。

核心原则：

```text
DXY / VIX / Nasdaq / Gold / Oil / OFR / rates 不再单独产生 BTC bullish/bearish driver。
```

## 范围

调整或新增 metric role：

```text
equity_beta
rates_pressure
dollar_pressure
volatility_stress
financial_stress
commodity_context
macro_impulse
btc_relative_confirmation
event_window
```

建议 registry 语义：

```python
direction = "composite_only" | "risk_context" | "context_only"
driver_eligible = False
affects_signal = False for raw metrics
affects_risk_flags = True for VIX / OFR / macro shock inputs
```

## 指标映射

```text
nasdaq / sp500 / russell_2000 / dow_jones -> equity_beta
us2y / us10y / real_yield / yield_curve -> rates_pressure
dxy_proxy -> dollar_pressure
vix -> volatility_stress
ofr_fsi -> financial_stress
gold / wti_oil / brent_oil -> commodity_context
macro event timing fields -> event_window
btc_vs_* / btc_beta_residual -> btc_relative_confirmation
```

## DoD

- `macro_radar` raw metrics 不再 `driver_eligible=True`。
- DXY、VIX、Nasdaq、Gold、Oil、OFR 不再单项进入 support/pressure drivers。
- P3 可以通过 role 获取各层输入。
- `module_weight`、`horizon_tags`、`duplicate_group_id` 与现有 P2 契约兼容。
- 旧版 `macro_radar` 可兼容读取，但默认 profile 指向 v3。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radars.py backend\tests\test_p3_pipeline.py -q
.\.venv\Scripts\python.exe -m compileall -q backend/src/onlybtc
```
