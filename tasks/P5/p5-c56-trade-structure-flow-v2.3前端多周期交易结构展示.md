# P5-C56 / Trade Structure Flow v2.3 前端多周期交易结构展示

## 状态

DONE

## Phase

P5 Vue3 前端应用

## 背景

前端需要展示 `trade_structure_flow v2.3` 的多周期交易结构、price acceptance、liquidity、spot/perp lead、leverage、liquidation response 和 residual，而不是让用户把单个成交量、funding、OI 或清算 spike 当成方向。

## 目标

Radar Detail 新增 v2.3 区块：

```text
Signal Stage / State
Multi Horizon: 5m / 15m / 1h
Liquidity
Aggressive Flow
Spot / Perp Lead
Leverage
Liquidation Response
BTC Response / Residual
Direction Boundary
```

## 展示规则

```text
signal_stage 区分 none / early_warning / fast_signal / confirmed_signal / conflict
trade_structure_state 优先于旧 aggressive_flow_state
multi_horizon 同屏展示 5m / 15m / 1h
liquidation_snapshot_only 作为 data quality flag 显示
Direction Boundary 明确单因子不能单独决定方向
```

## DoD

- [ ] trade_structure_flow detail 页面能展示 v2.3 四到八个结构区块。
- [ ] Dashboard module card 优先展示 signal_stage 与 trade_structure_state。
- [ ] 单因子禁语在前端说明中被替换为 price acceptance / residual 口径。
- [ ] 缺少 v2.3 字段时兼容旧展示。
- [ ] `npm run build` 通过。

## 关联任务

- P9-C35
- P4.5-C39
