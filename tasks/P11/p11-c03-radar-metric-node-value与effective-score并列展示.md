# P11-C03 / Radar Metric Node value 与 effective score 并列展示

## 状态
DONE

## 背景

Run Once 复审发现 Radar metric node 当前容易让用户把指标原始值和评分语义混在一起理解。例如 `btc_return_5m` 的原始 value 可能是 `-0.0011`，但该指标在 `trade_structure_flow` 中作为 price response confirmation context，`metric_effective_score=0.0`。

如果 UI 只突出其中一个字段，用户可能误以为“负收益值已经产生 bearish score”，或反过来误以为“score 0 表示指标值不存在”。

## 目标

在 Radar metric node 中同时展示原始值与 effective score：

```text
value -0.0011 · score 0
```

并保持节点布局紧凑，不改变当前结论链路。

## 范围

- 前端 Radar metric node / Evidence metric item 展示层。
- 优先使用已有 API 字段：
  - `value`
  - `metric_effective_score`
  - `metric_score`
  - `direction`
  - `score_bucket_v2`
- 不修改 P3/P4.5 评分逻辑。
- 不改变 final view、drivers、contract validation。

## DoD

- Radar metric node 同时显示 `value` 与 `score`。
- `score` 优先使用 `metric_effective_score`；缺失时 fallback 到 `metric_score`。
- context-only / confirmation context 指标可清楚看到 `value != 0` 但 `score = 0`。
- 文案紧凑，不挤压节点布局，不破坏移动端显示。
- 前端 build 通过。

## 执行记录

- `frontend/src/App.vue` 新增 `radarMetricValueScoreLine()`，Radar metric node 改为显示 `value ... · score ...`。
- score 优先取 `metric_effective_score`，缺失时 fallback 到 `metric_score`。
- `frontend/src/styles.css` 为节点分数行增加 nowrap/ellipsis，保持节点紧凑。

## 测试记录

```text
npm run build
vue-tsc -b && vite build passed
```
