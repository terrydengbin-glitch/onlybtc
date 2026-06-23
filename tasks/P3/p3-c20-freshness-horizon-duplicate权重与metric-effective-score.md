# P3-C20 Freshness / Horizon / Duplicate 权重与 metric_effective_score

## 状态

DONE

## 所属 Phase

P3 状态机、风险与事件窗口

## 任务目标

在 P3 scored evidence 中引入可审计的有效评分字段，使每个指标不只输出原始正零负分，还能输出进入 P4.5 聚合时的实际贡献：

- `freshness_weight`
- `horizon_weight`
- `duplicate_adjustment`
- `metric_effective_score`

该任务用于支撑 P4.5-C11 的聚合审计、周期视图、结论强度和 contract validation。

## 背景

P3-C16/P3-C18 已完成指标级正零负评分和 BTC 专业语义校准，但当前 P4.5 还无法稳定回答：

- 某个指标过期后是否应该降权。
- 某个指标在 24h / 3d / 7d 中贡献多少。
- 重复指标是否被重复计入最终结论。
- 最终 `core_view` 的强度是怎么从指标分数推出来的。

因此需要在 P3 层将原始分数转换为可聚合、可审计的 `metric_effective_score`。

## 实施范围

1. Freshness 权重
   - 从 P1/P8 metadata 读取：
     - `freshness_minutes`
     - `stale_after_minutes`
     - `is_stale`
   - 计算 `freshness_weight`。
   - 建议规则：
     - fresh -> `1.0`
     - expected lag -> `0.85` 到 `1.0`
     - stale -> `0.3` 到 `0.7`
     - missing freshness -> 默认 `1.0`，但输出 warning

2. Horizon 权重
   - 从 P2 metadata 读取 `horizon_tags`。
   - 针对不同输出周期计算 `horizon_weight`。
   - 支持至少：
     - `h24`
     - `d3`
     - `d7`
   - 没有周期标签时显式 warning。

3. Duplicate 降权
   - 从 P2 metadata 读取 `duplicate_group_id`。
   - 同一 duplicate group 的总贡献不得超过 group cap。
   - 输出 `duplicate_adjustment`。
   - 未配置重复组的指标默认 `1.0`。

4. Effective score
   - 每条 scored evidence 输出：

```text
metric_effective_score =
  metric_score
  * quality_score
  * freshness_weight
  * horizon_weight
  * duplicate_adjustment
```

5. P3 审计 HTML
   - 展示新增字段。
   - 展示每个 Radar module 的有效总分。
   - 展示缺字段 warning 和 duplicate group cap 结果。

## 输出契约

每条 scored evidence metadata 建议至少包含：

```json
{
  "metric_id": "btc_funding_rate",
  "metric_score": -0.12,
  "quality_score": 0.96,
  "freshness_weight": 1.0,
  "horizon_weight": 0.8,
  "duplicate_adjustment": 0.65,
  "metric_effective_score": -0.0599,
  "horizon_tags": ["h24", "d3"],
  "duplicate_group_id": "derivatives_funding_btc"
}
```

## 验收标准

- 每条 P3 scored evidence 都有 `metric_effective_score`。
- 能输出 `freshness_weight`、`horizon_weight`、`duplicate_adjustment`。
- module score 可基于 effective score 计算审计版总分。
- P3 HTML 能展示新增字段。
- 缺少 P1/P2 上游字段时输出 warning，不阻断 P3 产出。
- P4.5-C11 可直接消费这些字段，不需要再临时推断核心权重。

## 依赖任务

- P1-C36
- P2-C22
- P3-C16
- P3-C18
- P3-C19
- P4.5-C11
