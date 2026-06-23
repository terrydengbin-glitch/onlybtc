# P5-C40 BTC 决策卡多周期语义完整展示与条件措辞校准

## 状态

DONE

## 背景

最新 Run Once 后，Dashboard 中央 BTC 决策卡的主结论与后端 P4.5 deterministic 输出整体一致：

- `final_view = neutral / 中性观察`
- `trade_permission = watch_only`
- `confidence ≈ 0.46`
- `24h = bullish`
- `3d = bearish`
- `7d = bearish`

但前端展示还有两个容易误读的小问题：

1. BTC 卡片的 `3d / 7d` 区块当前只展示单个 `bearish`，没有明确同时展示 3d 与 7d 两个周期。
2. `反证：ETF 流出压力缓和`、`确认：偏空延续确认` 更像当前事实，实际它们是未来触发条件，需要明确为“反证条件 / 确认条件”。

## 目标

让 BTC 中央决策卡在不改变 P1/P2/P3/P4.5 后端契约的前提下，更准确地表达多周期结论和条件语义。

1. `24h` 区块继续展示短线方向。
2. `3d / 7d` 区块必须同时展示 3d 与 7d 的方向，例如 `3d bearish · 7d bearish`。
3. 反证入口文案改成条件表达，例如 `反证条件：ETF 流出若缓和`。
4. 确认入口文案改成条件表达，例如 `确认条件：偏空延续确认`。
5. 文案不得暗示反证或确认已经发生，除非后端明确返回 triggered / active 状态。
6. 保持中心 BTC 卡片布局不溢出，不破坏 3D tilt、金色 BTC 光效、拖拽连线和右侧摘要。

## 不改范围

- 不修改 P4.5 `horizon_views`、`invalidation_rules`、`confirmation_rules` 的生成逻辑。
- 不修改 P3 评分、P4.5 final_view 或 confidence。
- 不修改 Run Pipeline、LLM 开关或 Radar module 卡片逻辑。

## 实现要点

- 在 Vue3 前端增加多周期展示 helper：
  - `horizonPairText('d3', 'd7')`
  - 或等效实现。
- BTC 卡片中 `3d / 7d` 的 value 不再只读取 `horizonDirection('d3')`。
- 反证 / 确认按钮的标题优先使用条件措辞。
- 如果后端未来提供 `triggered=true`、`active=true`，前端再显示“已触发 / 已确认”；当前没有该字段时默认按“条件”展示。

## DoD

- [x] Dashboard BTC 卡片同时显示 3d 和 7d 方向。
- [x] `3d / 7d` 文案在窄宽度下不溢出 BTC 卡片。
- [x] 反证按钮不再把未来条件写成当前事实。
- [x] 确认按钮不再把未来条件写成当前事实。
- [x] 不影响 `final_view`、`confidence`、`trade_permission`、`risk_mode` 的原有映射。
- [x] `npm run build` 通过。

## 验收记录

- `frontend/src/App.vue`
  - 新增 `horizonPairDirection()`，BTC 决策卡 `3d / 7d` 区块改为同时展示两个周期方向。
  - 反证按钮文案改为 `反证条件：...`。
  - 确认按钮文案改为 `确认条件：...`。
- `frontend/src/styles.css`
  - 增加 `.mini-kv.horizon-pair strong` 小字号与行高，避免多周期文案挤出卡片。
- 验证：
  - `npm run build` 通过。

## 关联

P5-C02, P5-C32, P5-C34, P5-C38, P4.5-C12, P4.5-C21
