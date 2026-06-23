# P2-C32 / Treasury Credit v2.1 registry role / composite-only / risk-context

## 状态

DONE

## 目标

将 `treasury_credit` 从单指标方向加权，升级为 role-based composite 模块。

## 范围

- 原始 level 指标设置为 `composite_only` 或 `risk_context`。
- 新增 role：
  - `policy_rate_pressure`
  - `real_yield_pressure`
  - `duration_term_pressure`
  - `curve_regime`
  - `inflation_mix`
  - `credit_stress`
- 派生指标参与组合状态机，但不得单独生成“2Y 高所以 BTC bearish”之类 driver。

## DoD

- `treasury_2y`、`treasury_10y`、`real_yield_10y`、`hy_spread` 等 raw level 权重为 0 或不直接影响方向。
- HY / IG OAS 作为 credit/risk context，而不是独立多空因子。
- derived metric 带 horizon tags 与 role。

## Execution Record

- DONE: added MetricRole entries for Treasury Credit v2.1.
- DONE: updated radar registry roles, weights, horizon tags and driver eligibility.
- RECOVERY NOTE 2026-05-26: P2 registry direction isolation is in place; P3 still needs BTC response sub-state alignment before the full chain can be marked recovered.
