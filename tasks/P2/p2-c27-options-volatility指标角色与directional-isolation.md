# P2-C27 / Options Volatility 指标角色与 directional isolation

## 状态

DONE

## 背景

`options_volatility` 不是方向 alpha 模块。它用于识别波动风险、保护需求、尾部风险、到期压力与 pinning 结构，不应通过通用 radar metric rule 改变 BTC final direction。

## 目标

将 options 指标统一纳入风险结构角色：

```text
volatility_regime:
  options_iv
  options_rv

protection_demand:
  put_call_ratio

tail_risk:
  options_skew

expiry_pressure:
  options_expiry_notional

pinning_structure:
  max_pain_distance
  gamma_wall_proxy_distance
```

## 契约要求

所有 `options_volatility` 指标默认：

```text
affects_signal = false
driver_eligible = false
affects_risk_flags = true
direction = composite_only / context_risk
weight = 0 for directional score
```

禁止单指标进入：

```text
support_drivers
pressure_drivers
directional_score
bullish/bearish majority vote
```

## DoD

- Registry 支持 `volatility_regime`、`protection_demand`、`tail_risk`、`expiry_pressure`、`pinning_structure` 角色。
- options 指标不再作为单独 bullish / bearish driver。
- `module_score` 默认不被 P2 通用规则推偏。
- P2/P3 contract tests 通过。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radars.py -q
```
