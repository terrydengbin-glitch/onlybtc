# P5-C39 / Radar Module 复合状态优先展示与 Fund Flow 语义防误导

## 状态

DONE

## 背景

最新审计发现后端 Fund Flow 与 Kline Orderflow 的复合语义已经正确：

- Fund Flow:
  - `module_direction = bearish`
  - `module_effective_direction = bullish`
  - `fund_flow_state = bearish_but_improving`
  - 真实含义是“绝对资金面偏空，但边际改善”。
- Kline Orderflow:
  - `module_effective_direction = bullish`
  - `trend_state = neutral_wait_confirm`
  - 真实含义是“短线有正向分数，但量价结构尚未确认方向”。

但前端 Radar 卡片优先展示 `module_effective_direction`，导致 Fund Flow 被显示为纯 `bullish`，Kline 也被显示为纯 `bullish`，和后端复合状态不一致。

## 目标

1. Radar 模块卡片优先显示 `fund_flow_state` / `trend_state` / 关键 `module_state`。
2. 不直接把 `module_effective_direction = bullish` 当成主标签。
3. Fund Flow 显示为“偏空但改善 / bearish but improving”。
4. Kline Orderflow 在 `trend_state=neutral_wait_confirm` 时显示“等待确认”，不显示纯 bullish。
5. 颜色使用 `mixed` 或 pressure-easing 风格，避免误用纯绿色 support。
6. 指标节点仍保留真实结构，例如 Fund Flow 里 3 个 bearish + 1 个 bullish。

## 不改范围

- 不修改 P2/P3/P4.5 后端评分与聚合逻辑。
- 不修改 Evidence 详情。
- 不修改 Run Pipeline。

## DoD

- [x] Dashboard 拓扑节点标签使用复合状态。
- [x] Radar Detail 模块按钮使用复合状态。
- [x] Radar Detail 中心卡使用复合状态。
- [x] Fund Flow 不再展示为纯 `bullish`。
- [x] Kline Orderflow 不再在 `neutral_wait_confirm` 时展示为纯 `bullish`。
- [x] `npm run build` 通过。

## 验收记录

- `frontend/src/App.vue`
  - 新增 `moduleDisplayState()` / `moduleDisplayLabel()` / `moduleDisplayClass()`。
  - 展示优先级：`fund_flow_state` -> `trend_state` -> 有意义的 `module_state` -> `module_effective_direction` -> `module_direction`。
  - `bearish_but_improving`、`neutral_wait_confirm` 等复合状态按 mixed 类展示，避免纯绿色 support 误导。
  - Dashboard 拓扑节点、Radar Detail 模块按钮、Radar Detail 中心卡均改为复合状态展示。
  - Fund Flow 文案明确为“绝对偏空但边际改善”。
  - Kline Orderflow 文案明确为“短线分数偏正但量价结构等待确认”。
- 验证：
  - `npm run build`
  - 结果：通过。
