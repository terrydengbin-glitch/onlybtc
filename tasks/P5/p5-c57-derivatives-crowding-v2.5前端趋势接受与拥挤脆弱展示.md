# P5-C57 / Derivatives Crowding v2.5 前端趋势接受与拥挤脆弱展示

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

前端需要展示 `derivatives_crowding v2.5` 的趋势先验、杠杆接受、拥挤脆弱、squeeze risk、funding/OI/positioning/liquidation 子状态和方向边界，而不是让用户把 funding、OI、多空比或清算 spike 当成单独方向。

## 展示区块

```text
1. Signal Stage / Derivatives State
2. Trend Prior / BTC Response
3. Trend Acceptance / Crowding Fragility / Squeeze Risk
4. Funding / OI Participation / Positioning
5. Liquidation Response: follow-through vs absorbed
6. Direction Boundary / 禁语说明
```

## DoD

- [ ] Radar detail 展示 v2.5 六区块。
- [ ] 顶部 semantic stats 展示 stage/state/BTC implication。
- [ ] 保留旧 derivatives_crowding 字段兼容。
- [ ] 前端文案明确 funding/OI/long-short/liquidation 不是单因子方向。
- [ ] `npm run build` 通过。

## 依赖

- P9-C36
- P4.5-C40
