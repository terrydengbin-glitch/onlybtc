# P5-C43 / BTC Total State v2 四区块展示与方向防误导

## 状态
DONE

## 背景

P3-C41 / P4.5-C26 / P9-C24 会提供 `btc_total_state v2` 分层字段。前端 Radar Detail 需要把方向信号、合约确认、周期背景和审计上下文分开展示，避免用户误以为 Halving / Block Height / Funding / OI 都在直接影响 24h 方向。

## 目标

Radar Detail 中 `btc_total_state` 展示四块：

```text
短线方向
合约确认
周期背景
数据审计
```

## 展示要求

```text
短线方向:
  btc_short_term_state
  price_state.state / strength / basis

合约确认:
  perp_state.state
  confirmation
  risk_state
  funding / OI basis

周期背景:
  halving_context_only
  不显示为 direction driver

数据审计:
  block_height_synced / stale / missing
  不显示为 direction driver
```

## 防误导要求

- 不展示“funding positive 所以 bullish”。
- 不展示“OI 高所以 bullish/bearish”。
- 不把 `btc_halving_estimated_days` 和 `btc_block_height` 放进方向驱动列表。
- Metric node 可结合 P11-C03 显示 `value · score`，帮助用户区分原始值和有效分。

## DoD

- Radar Detail 对 `btc_total_state` 使用四区块布局。
- 缺失 v2 字段时能 fallback 到旧版 module summary。
- 移动端不重叠、不溢出。
- 前端 build 通过。

## 执行记录

- `frontend/src/App.vue` 为 `btc_total_state` Radar Detail 增加四区块展示：短线方向、合约确认、周期背景、数据审计。
- `btc_total_state` 支持 `btc_total_state_v2`、顶层 v2 字段、`module_semantic_profile` 三种来源 fallback。
- 模块摘要改为 `price_state + perp_state` 组合语义，并明确 Halving / Block Height 仅为 context/audit。
- `frontend/src/styles.css` 增加响应式四区块样式，移动端降为单列避免溢出。

## 测试记录

```text
npm run build
vue-tsc -b && vite build passed
```
