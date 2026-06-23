# P2-C28 / Event Policy 指标角色与 risk-only 隔离

## 状态
DONE

## 背景

事件窗口指标会影响交易许可、风险锁定与信心折扣，但不应通过通用 radar metric rule 改变 BTC 方向。

## 目标

将 `event_policy` 指标统一纳入 risk-only 角色：

```text
macro_data_event:
  cpi_days_until
  pce_days_until
  nfp_days_until

fomc_policy_event:
  fomc_days_until

fed_speech_event:
  next_fed_speech_hours_until
  fed_speech_scheduled_risk

blackout_context:
  fomc_blackout_active
```

## Registry 契约

所有 event_policy 指标默认：

```text
weight = 0.0
direction = context_risk
affects_signal = false
affects_confidence = false
affects_risk_flags = true
driver_eligible = false
score_bucket = event_context / risk_only
```

## 禁止行为

```text
CPI 临近 -> bearish
FOMC 临近 -> bearish
Fed speech scheduled risk 高 -> bearish
blackout active -> bearish
```

## DoD

- Registry 支持 `macro_data_event`、`fomc_policy_event`、`fed_speech_event`、`blackout_context` role。
- event_policy 指标不进入 support_drivers / pressure_drivers。
- event_policy 指标不参与 directional_score 或 bullish/bearish majority vote。
- P2 输出可被 P3 profile 消费为事件风险上下文。
- P2/P3 contract tests 通过。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radars.py -q
```
