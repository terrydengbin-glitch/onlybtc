# P5-C60 Invalidation / Confirmation Workbench v2 前端展示

状态：DONE

## 目标

把 `Invalidation / Confirmation` 子页面从规则列表升级为验证台，前端优先消费 `p45.invalidation_workbench.v2`，展示当前 BTC thesis 是否被确认、证伪、冲突、阻断或仍在等待。

## 页面结构

```text
0. Validation Banner
   validation_state + validation_reason

1. Current Thesis
   BTC Cockpit 当前观点、方向、质量、置信、交易许可、4h/24h/3d/7d

2. BTC Response
   price acceptance、residual、micro response、failed attempts

3. Confirmation Lane
   confirm_current_view / upgrade_scenarios

4. Invalidation Lane
   refute_current_view / downgrade_scenarios / break_neutral_scenarios

5. Evidence Matrix
   14 modules 按 layer 显示 accepted / rejected / conflict / missing / stale / blocked

6. Trigger Timeline
   not_armed -> arming -> armed -> triggered / rejected / expired
```

## UI 规则

1. `confirmed` 用支撑色，`refuted` 用压力色，`conflict` 用 mixed 色，`blocked` 用 data-quality 色。
2. `triggered_rules` 与 `armed_rules` 分区展示，避免用户把 armed 当成已触发。
3. Evidence Matrix 必须明确显示模块是 `accepted`、`rejected`、`conflict`、`missing`、`stale` 还是 `blocked`。
4. BTC response 缺失时，页面文案必须显示“等待 BTC response / residual 裁决”，不能显示已确认。
5. 保留旧 `invalidation_rules` / `confirmation_rules` fallback。

## 不改范围

```text
Dashboard 拓扑页
Radar 子页面
BTC cockpit 中心卡
P4.5 研报正文
```

## DoD

1. 前端优先读取 `state.invalidation.schema_version = p45.invalidation_workbench.v2`。
2. v2 存在时渲染 Validation Banner、Current Thesis、BTC Response、Confirmation Lane、Invalidation Lane、Evidence Matrix、Timeline。
3. v2 缺失时 fallback 到旧规则列表。
4. blocked / stale / missing 有明确视觉提示。
5. `npm run build` 通过。
6. P5 dashboard contract 验收通过。
