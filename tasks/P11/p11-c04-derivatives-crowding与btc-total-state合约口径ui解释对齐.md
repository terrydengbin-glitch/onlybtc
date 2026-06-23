# P11-C04 / derivatives_crowding 与 BTC Total State 合约口径 UI 解释对齐

## 状态：DONE

## 背景

`btc_total_state` v2 中 funding / OI 只作为 `price_state + perp_state` 的组合输入，不单独生成 BTC 24h 方向 driver。

`derivatives_crowding` 仍会展示 `btc_funding_rate` / OI 相关贡献，这是该模块的职责：分析合约拥挤、杠杆热度、清算和 squeeze risk。

## 目标

在 UI 解释层区分两个模块口径：

```text
btc_total_state:
  funding / OI 只参与 price + perp 组合判断。

derivatives_crowding:
  funding / OI 用于合约拥挤、杠杆热度和 squeeze risk。
```

## 已完成

- Radar Detail 为 `derivatives_crowding` 增加 Derivatives Scope 说明。
- `derivatives_crowding` 模块摘要明确 funding/OI 是 derivatives risk inputs，不是 BTC Total State direction drivers。
- 当在 `derivatives_crowding` 中选中 `btc_funding_rate` 或 `btc_open_interest` 时，展示 Funding / OI Scope 说明。
- `btc_total_state` 继续保留 v2 四区块和 Direction Boundary，不回退到 raw funding/OI 单指标方向解释。

## DoD

- [x] UI 中用户能区分 `btc_total_state` 与 `derivatives_crowding` 对 funding/OI 的不同用途。
- [x] `btc_total_state` 不展示 `funding positive -> bullish` 或 `OI high -> bullish/bearish` 单指标方向文案。
- [x] `derivatives_crowding` 的 funding/OI 展示明确为拥挤、杠杆热度或风险确认口径。
- [x] Dashboard / Radar Detail 不再让用户误以为两个模块在重复计算同一个方向 driver。
- [x] 前端构建通过。

## 验证

```text
npm run build
passed
```
