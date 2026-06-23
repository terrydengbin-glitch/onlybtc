# P1-C49 / Treasury Credit v2.1 派生指标与历史窗口准备

## 状态

DONE

## 目标

为 `treasury_credit.v2.1` 准备利率、实际利率、曲线、信用利差与 BTC residual 的派生指标，使下游可以判断：

```text
美债/信用环境是否正在确认、削弱或反证 BTC 4h-3d 趋势。
```

## 范围

- 新增 `treasury-credit-derived` derived-only source。
- 新增 `ig_oas` FRED 指标。
- 派生：
  - 2Y / 10Y / 30Y 变化与 z-score。
  - 10Y real yield、10Y breakeven 变化。
  - 2s10s / 10s30s 曲线与曲线变化。
  - HY OAS 1d/5d 变化、60d z-score、252d percentile。
  - BTC expected return、BTC residual 与 rates/credit residual。

## DoD

- raw level 指标和 derived 指标均进入 P1/P2 可消费指标表。
- 周频/日频宏观指标不与 BTC 高频价格硬混用，只输出分层派生结果。
- 缺少历史窗口时不输出强假值。
- 单元测试覆盖曲线、信用与 BTC residual 派生。

## Execution Record

- DONE: registered `treasury-credit-derived` and `fred-ig-oas`.
- DONE: added Treasury Credit v2.1 derived metrics in source service.
- Verified: `test_treasury_credit_derived_metrics_include_curve_credit_and_btc_residual` passed.
- RECOVERY NOTE 2026-05-26: optional items still need explicit future-scope decision if required: term premium, CCC OAS, HY-IG gap, `ig_oas_change_5d_bps`, and `btc_vs_ndx_residual_24h`.
- AUDIT NOTE 2026-05-26: initial Run Once output did not include `treasury-credit-derived` rows for `collect-20260526082847-cef1c0`; manually reran Treasury Credit derived backfill, producing 39 derived metric rows for the collect run.
