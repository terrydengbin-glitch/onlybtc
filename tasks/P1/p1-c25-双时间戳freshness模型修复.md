# P1-C25 双时间戳 Freshness 模型修复

## 状态

DONE

## 来源

P1-C22 真实数据全链路验收复跑后仍存在非阻断问题：

```text
freshness: stale=5, expired=35
```

进一步检查发现，大量 stale / expired 并不是采集失败，而是当前系统把两类时间混在一起：

- `collected_at`：onlyBTC 本轮什么时候成功采集到数据。
- `observed_at`：数据源业务数据本身对应的发布时间或观测时间。

FRED、CoinMetrics、OFR、Fed、Bitbo、Glassnode 页面类数据本身就是日更、周更、月更或事件型。如果用统一的 10 分钟 / 60 分钟规则判断，会把正常的低频数据误判为过期。

## 所属 Phase

P1 数据源与历史数据底座 / P2 Radar / P5 Data Quality / P8 SQLite

## 当前问题

当前 freshness 语义不够清晰：

```text
metric_values.ts 既承担业务观测时间，又被用于数据管道新鲜度判断。
```

这会导致：

- 采集刚刚成功，但业务数据是昨日或上周数据时，被判定为 expired。
- Radar quality 被误伤拉低。
- P1-C22 指标参数清单显示大量 expired，但实际上没有采集失败。
- LLM 可能把正常低频宏观数据误读成数据质量差。

## 目标

建立双时间戳模型：

```yaml
time_model:
  collected_at:
    meaning: 本系统采集成功时间
    use_for:
      - pipeline_health
      - source_health
      - run_logs
      - collection_freshness

  observed_at:
    meaning: 源数据业务观测时间
    use_for:
      - historical_window
      - feature_calculation
      - trend_analysis
      - business_recency
```

## 修复要求

### 1. 标准化样本字段

每个 `MetricSample` / 标准化指标需要明确输出：

```yaml
metric_id: dxy_proxy
value: 104.12
observed_at: 2026-05-19T00:00:00Z
collected_at: 2026-05-20T14:03:09Z
source_id: fred-macro
run_id: collect-...
```

如果源数据只提供当前值，不提供业务时间：

```yaml
observed_at: collected_at
observed_at_source: inferred_from_collection_time
```

### 2. Freshness 拆分

输出两个状态：

```yaml
collection_freshness:
  status: fresh | stale | expired | missing
  reason: did_onlybtc_collect_recently

business_recency:
  status: current | lagging | outdated | unknown
  reason: is_source_business_timestamp_expected
```

### 3. Audit 报告修复

P1-C22 指标参数清单需要区分：

- 采集新鲜度
- 业务时间新鲜度
- 当前行 source
- selected source

避免出现“某一行 source expired，但备注来自 selected source fresh”的混淆。

## DoD

- 所有 `MetricSample` 都能携带或推导 `collected_at` 与 `observed_at`。
- `historical_window(metric_id)` 返回 `collection_freshness` 与 `business_recency`。
- Data Quality 快照不再只依赖业务时间戳判断管道健康。
- P1-C22 报告能分开展示两类 freshness。
- 对 FRED / CoinMetrics / Fed / 页面类数据，采集成功时不再因为业务时间戳低频而被误判为管道 expired。
- 测试覆盖：
  - 高频实时数据：`observed_at ~= collected_at`。
  - 日更数据：`observed_at` 较旧但 `collection_freshness=fresh`。
  - 真正未采集数据：`collection_freshness=missing/expired`。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode live
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit --no-collect-live
..\.venv\Scripts\python.exe -m pytest
```

## 本次执行结果

已完成：

- 保留兼容字段 `freshness_status`，语义调整为采集新鲜度。
- 新增业务时间语义：
  - `business_recency_status`
  - `business_age_seconds`
  - `business_recency_discount`
- Source Health message 同时记录 collection freshness 与 business recency。
- P1-C22 不再把日更/周更数据误判为采集过期。

复跑 P1-C22 结果：

```text
collection freshness: {'fresh': 53, 'stale': 0, 'expired': 0, 'missing': 0}
business recency: {'current': 53, 'lagging': 0, 'outdated': 0, 'unknown': 0}
```
