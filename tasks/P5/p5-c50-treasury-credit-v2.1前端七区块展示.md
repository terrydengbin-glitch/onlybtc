# P5-C50 / Treasury Credit v2.1 前端七区块展示

## 状态

DONE

## 目标

在 Radar Detail 前端为 `treasury_credit` 展示七个专业区块，避免把美债/信用 raw metric 误读成单因子方向。

## 展示区块

1. Policy Rate Pressure
2. Real Yield Pressure
3. Duration / Term Pressure
4. Curve Regime
5. Inflation Mix
6. Credit Stress
7. BTC Response Confirmation

## DoD

- 顶部 summary 优先使用 `treasury_credit_state`。
- 七区块展示 state / score / basis。
- 展示 `early_warning_flags` 与 `data_quality_flags`。
- metric label 覆盖 Treasury Credit v2.1 派生指标。
- `npm run build` 通过。

## Execution Record

- DONE: added Treasury Credit v2.1 UI contract and seven-card detail view.
- DONE: added frontend labels and semantic summary.
- Verified: `npm run build` passed.
- RECOVERY NOTE 2026-05-26: Vue3 display contract exists; rerun build after P3/P9 contract is finalized.
- Verified 2026-05-26: `npm run build` passed.
