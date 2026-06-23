# P1-C36 source_ts / collected_at 与 Freshness 字段贯穿 P1/P8

## 状态

DONE

## 所属 Phase

P1 数据源与采集层 / P8 SQLite 数据中心与历史底座

## 任务目标

为后续 P4.5 Research Report V2 的 freshness 权重、数据过期判断和审计展示补齐上游字段，在 P1 采集和 P8 SQLite 持久化层贯穿：

- `source_ts`
- `collected_at`
- `freshness_minutes`
- `stale_after_minutes`
- `is_stale`

## 背景

P4.5-C11/C12 需要判断每条 evidence 的数据是否新鲜，进而影响：

- `freshness_weight`
- `metric_effective_score`
- `contract_validation.warnings`
- HTML 中的数据质量与过期提示

当前 P1/P8 已有双时间戳语义和 freshness policy 基础，但 P4.5 v2 需要更统一、可消费、可审计的字段契约。

## 实施范围

1. P8 schema / metadata 契约
   - 确认 `raw_observations`、`metric_values`、`feature_values.metadata_json` 是否能保存：
     - `source_ts`
     - `collected_at`
     - `freshness_minutes`
     - `stale_after_minutes`
     - `is_stale`
   - 如需新增字段或迁移，优先兼容既有数据。
   - 保留现有 `collection_freshness_status` 与 `business_recency_status` 语义。

2. P1 采集层
   - 每个 source run 明确：
     - 来源业务时间 `source_ts`
     - 本地采集时间 `collected_at`
   - 按 provider freshness policy 计算：
     - `freshness_minutes`
     - `stale_after_minutes`
     - `is_stale`
   - 对页面源、API 源、fallback 源保持统一字段。

3. P1-C22 审计 HTML
   - 展示上述字段。
   - 区分：
     - 采集新鲜度
     - 业务时间新鲜度
     - provider 发布节奏允许的 expected lag

4. 向 P2/P3/P4.5 传递
   - P2/P3 能从 metric/evidence metadata 读取 freshness 字段。
   - 若某 source 暂时没有 `source_ts`，必须显式标记 unknown，不可静默缺失。

## 输出契约

每条 metric/evidence metadata 至少可提供：

```json
{
  "source_ts": "2026-05-22T00:00:00Z",
  "collected_at": "2026-05-22T06:48:41Z",
  "freshness_minutes": 408,
  "stale_after_minutes": 1440,
  "is_stale": false,
  "freshness_status": "fresh",
  "business_recency_status": "expected_lag"
}
```

## 验收标准

- P1 live 采集后，主要 metric metadata 有 `source_ts` 和 `collected_at`。
- 能计算 `freshness_minutes`、`stale_after_minutes`、`is_stale`。
- fallback / historical fallback 的 freshness 状态显式可见。
- P1-C22 HTML 显示 freshness 字段。
- P3 scored evidence 可继承 freshness metadata，供 P4.5-C11 使用。
- 缺字段时输出 warning，不静默吞掉。

## 依赖任务

- P1-C25
- P1-C26
- P1-C34
- P8-C15
- P4.5-C11
