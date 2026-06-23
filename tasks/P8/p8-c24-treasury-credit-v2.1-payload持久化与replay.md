# P8-C24 / Treasury Credit v2.1 payload 持久化与 replay

## 状态
DONE

## 背景

`treasury_credit.v2.1` 新增多层结构化 payload。SQLite 与 replay 链路需要保证最新 run、历史回放、Radar Detail 和 Final Report 都不会丢失字段。

## 目标

确保以下 payload 可被持久化与回放：

```text
semantic_profile_version
module_purpose
timeframe
states.policy_rate_pressure
states.real_yield_pressure
states.duration_term_pressure
states.curve_regime
states.inflation_mix
states.credit_stress
states.btc_response_confirmation
treasury_credit_state
module_direction
module_score
module_effective_score
risk_score
confidence_adjustment
btc_implication
support_drivers
pressure_drivers
risk_drivers
early_warning_flags
data_quality_flags
context_notes
summary
```

## DoD

- P3 scored module payload carries complete `treasury_credit.v2.1` profile.
- P4.5 final payload keeps `treasury_credit_explanation`.
- Radar Detail replay can restore `treasury_credit_v21`.
- Old runs without v2.1 fields fall back to legacy display without API error.
- SQLite/replay tests cover latest and historical paths.

## 验证建议

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py backend\tests\test_p45_final_writer.py -k treasury_credit -q
```

## Execution Record

- TODO: verify latest and replay paths after P3 state machine test passes.
- RECOVERY NOTE 2026-05-26: keep this card open until the P3 semantic profile test passes and replay/API payload preservation is rechecked.
- DONE 2026-05-26: P3 semantic profile test passes and dashboard/final writer payload path was rechecked.
- Verified: `.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py backend\tests\test_p45_final_writer.py -k "treasury_credit or dashboard" -q` -> 23 passed, 9 deselected.
