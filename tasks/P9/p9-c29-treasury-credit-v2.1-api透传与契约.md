# P9-C29 / Treasury Credit v2.1 API 透传与契约

## 状态
DONE

## 背景

FastAPI 聚合层需要把 `treasury_credit.v2.1` 结构化字段稳定透传给 Dashboard、Radar Detail、Evidence 和 History Replay。

## 目标

扩展 API 契约，暴露：

```text
treasury_credit_v21
treasury_credit_state
timeframe
states
btc_implication
risk_score
confidence_adjustment
support_drivers
pressure_drivers
risk_drivers
early_warning_flags
data_quality_flags
context_notes
display_state
display_summary
```

## DoD

- `/api/p45/radar-modules/treasury_credit` 返回 `treasury_credit_v21`。
- `/api/p45/dashboard/latest` modules 列表保留 `treasury_credit_state` 和 display state。
- v2.1 profile 的 direction/score 覆盖 legacy fallback。
- API 对旧 run 兼容，不因缺少 `treasury_credit_v21` 报错。
- Contract test 覆盖 latest 和 detail。

## 验证建议

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -k treasury_credit -q
```

## Execution Record

- PARTIAL: `_project_treasury_credit_v21` exists and exposes `treasury_credit_v21`.
- VERIFIED PARTIAL: `test_p45_dashboard_api.py -k treasury_credit` passed in recovery check.
- TODO: rerun API contract after P3 state machine is fixed.
- DONE 2026-05-26: reran API contract after P3 recovery.
- Verified: `.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -k treasury_credit -q` -> 1 passed, 22 deselected.
- AUDIT NOTE 2026-05-26: latest API detail points to corrected lineage `radar-20260526083837-9b5e59` / `p3-20260526083838-ee71bd` / `p45final-20260526083844-0e7a90` and exposes `treasury_credit_v21`.
