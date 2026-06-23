# P3-C47 / Treasury Credit v2.1 状态机、warning 前置与 BTC residual

## 状态

DONE

## 目标

新增 `p3.c47.treasury_credit.v2.1` profile，使模块回答：

```text
rates / real yield / curve / credit 是否确认、削弱或反证 BTC 当前趋势？
BTC 是否正在吸收、拒绝或抵抗外部 rates/credit 信号？
```

## 状态机

- `rates_tailwind_confirmed`
- `rates_headwind_warning`
- `rates_headwind_confirmed`
- `credit_widening_warning`
- `credit_stress_confirmed`
- `btc_resisting_rates_headwind`
- `btc_rejecting_rates_tailwind`
- `reflation_supportive`
- `curve_growth_scare`
- `treasury_credit_neutral`

## DoD

- 输出 `states.policy_rate_pressure / real_yield_pressure / duration_term_pressure / curve_regime / inflation_mix / credit_stress / btc_response_confirmation`。
- 输出 `treasury_credit_state / module_direction / module_score / risk_score / confidence_adjustment / btc_implication`。
- warning 状态早于 confirmed 状态触发。
- BTC residual 影响“抗逆风/拒绝顺风”的分类。
- 原始 level 指标不直接写成单因子因果结论。

## Execution Record

- DONE: added Treasury Credit v2.1 semantic profile.
- DONE: added score override, direction override and state summary in P3 aggregation.
- RECOVERY NOTE 2026-05-26: crash recovery found the current targeted test failing.
- BLOCKED: `test_treasury_credit_v21_warning_and_btc_residual_states` currently produces `treasury_credit_state=btc_resisting_rates_headwind` while `states.btc_response_confirmation.state=btc_credit_neutral`; expected sub-state is `btc_resisting_headwind`.
- TODO: align BTC response sub-state thresholds with total state thresholds, then rerun `.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -k treasury_credit -q`.
- RESOLVED 2026-05-26: targeted recovery test now passes; BTC response sub-state aligns with `btc_resisting_rates_headwind`.
- Verified: `.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -k treasury_credit -q` -> 1 passed, 32 deselected.
- AUDIT NOTE 2026-05-26: corrected chain `p3-20260526083838-ee71bd` emits `semantic_profile_version=p3.c47.treasury_credit.v2.1`, `treasury_credit_state=treasury_credit_neutral`, `btc_response_confirmation=btc_rejecting_tailwind`, `module_score=-0.0675`, `risk_score=35.0`.
