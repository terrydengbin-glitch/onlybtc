# P3-C23 Radar Module 聚合器升级：Coverage / Conflict / Confidence

## 状态

DONE

## 所属 Phase

P3 算法、事件窗口与评分层

## 背景

P3-C21 审计发现，当前模块分主要使用：

```text
module_score = Σ metric_score
module_effective_score = Σ metric_effective_score
```

这会带来两个问题：

1. 指标数量多的模块更容易得到较大绝对分，指标少的模块容易被压平。
2. raw direction 与 effective direction 冲突时，当前缺少显式 conflict 解释。

例如资金流可能出现：

```text
raw module_score < 0
module_effective_score > 0
```

这种情况不能简单显示 bullish 或 bearish，而应标记为方向冲突、压力缓和或改善中。

## 上下游对齐

| Phase | 契约关系 |
| --- | --- |
| P1/P8 | 继续提供 source quality、freshness、run lineage、source conflict。 |
| P2 | 继续提供 `module_weight`、`duplicate_group_id`、`horizon_tags`、metric role。 |
| P3-C22 | 提供更准确的指标级 `metric_score`、组合规则和 risk overlay。 |
| P3-C23 | 在模块层做聚合审计，不改变 P1/P2/P8 原始数据。 |
| P4.5 | 消费新的 module aggregation audit，用于 decision_card、horizon_views、research_article。 |
| P5/P9 | 前端展示 module coverage/conflict/top contributors，不做计算。 |

## 任务目标

升级 P3 module output，使每个 Radar module 输出：

```yaml
module_raw_score:
module_effective_score:
module_confidence:
coverage_score:
conflict_score:
freshness_score:
top_positive:
top_negative:
top_contributors:
raw_effective_conflict:
module_state:
```

## 聚合公式建议

```text
module_raw_score =
  Σ(metric_score * metric_weight) / Σ(active_metric_weight)

module_confidence =
  quality_score
  * coverage_score
  * freshness_score
  * conflict_penalty

module_final_score =
  module_raw_score * module_confidence
```

字段解释：

| 字段 | 含义 |
| --- | --- |
| `coverage_score` | 有效指标权重 / 应有指标权重 |
| `conflict_score` | 正负分冲突程度 |
| `freshness_score` | 模块内指标新鲜度聚合 |
| `module_confidence` | 质量、覆盖、新鲜度、冲突后的可信度 |
| `top_contributors` | 对模块方向贡献最大的指标 |

## Conflict 规则

```text
if sign(module_score) != sign(module_effective_score)
and abs(module_score) > 0.08
and abs(module_effective_score) > 0.03:
    raw_effective_conflict = true
    module_state = conflict / improving / deteriorating
    module_confidence *= 0.65
```

示例解释：

```text
资金流：方向冲突。
ETF 净流出仍偏空，但交易所余额下降缓和了卖压。
结论：bearish but improving，不支持强看多。
```

## DoD

- 每个 Radar module 都输出 `coverage_score`。
- 每个 Radar module 都输出 `conflict_score`。
- 每个 Radar module 都输出 `module_confidence`。
- 每个 Radar module 都输出 `top_positive/top_negative/top_contributors`。
- raw/effective 方向冲突能被显式标记。
- P4.5 能消费新字段，不破坏旧字段。
- P3 HTML 能展示聚合审计字段。
- P5 Radar Detail / Dashboard 可读取并展示这些字段。
- 全量 P1/P2/P3/P4.5 跑通。

## 关联任务

P3-C20, P3-C21, P3-C22, P3-C24, P4.5-C11, P4.5-C12, P5-C17


## 执行记录

- 已在 P3 scored radar module 输出中新增 `module_raw_score`、`module_final_score`、`coverage_score`、`conflict_score`、`freshness_score`、`quality_score`、`conflict_penalty`。
- 已将 `module_confidence` 改为基于 quality / coverage / freshness / conflict penalty 的聚合置信度，并保留 `source_module_confidence`。
- 已新增 `raw_effective_conflict` 和 `module_state`，能标记 raw/effective 方向冲突以及 improving / deteriorating / internal_conflict 等状态。
- 已新增 `top_positive`、`top_negative`、`top_contributors` 结构化字段，便于 P4.5 研报和 P5 Radar Detail 解释模块主导因子。
- 已将新字段加入 P3 full-chain audit row / HTML 表头，并在 P4.5 HTML module rows 中透出。
- 已扩展 P3 pipeline 测试，验证 module row 含 coverage/conflict/freshness/raw/final/top contributors 字段。

## 验证结果

```text
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p3_pipeline.py -q
15 passed in 5.74s

.\.venv\Scripts\python.exe -m py_compile backend/src/onlybtc/algorithms/p3.py backend/src/onlybtc/audit/p3_full_chain.py backend/src/onlybtc/p45/html_report.py
passed
```
