# P8-C15 SQLite 双时间戳与 Freshness Policy 持久化

## 状态

DONE

## 来源

P1-C25 / P1-C26 需要在采集与质量判断层区分：

- `collected_at`
- `observed_at`
- `collection_freshness`
- `business_recency`
- `freshness_policy`

SQLite 当前表结构和 repository 查询需要承接这些字段，否则 Radar、P1-C22、Data Quality 页面无法稳定复用。

## 所属 Phase

P8 SQLite 数据库与持久化层 / P1 数据源 / P5 Data Quality / P2 Radar

## 当前问题

当前 `metric_values.ts` 已经承载时序用途，但缺少明确的数据语义：

```text
ts 是业务观测时间，还是采集落库时间？
```

同时 freshness policy 大多在代码逻辑里隐式存在，不利于审计与 UI 展示。

## 目标

SQLite 层支持双时间戳与 policy 查询：

```yaml
metric_values:
  observed_at: datetime
  collected_at: datetime
  run_id: string
  metric_id: string
  source_id: string

metric_quality_snapshot:
  collection_freshness_status: fresh
  business_recency_status: current
  freshness_policy_id: daily_fred
```

## 推荐实现

优先兼容现有 schema：

1. 如果已有 `ts`，保留其业务含义为 `observed_at`。
2. 新增或通过 metadata 写入：
   - `collected_at`
   - `observed_at_source`
   - `freshness_policy`
3. repository 层统一输出标准字段，避免 UI 直接猜数据库字段语义。

如果需要迁移：

```text
metric_values.observed_at
metric_values.collected_at
metric_values.observed_at_source
metric_values.freshness_policy_id
```

也可以先用 `metadata_json` 过渡，但 DoD 必须保证查询输出稳定。

## Repository 要求

查询服务必须返回：

```yaml
metric_value:
  metric_id: dxy_proxy
  value: 104.12
  observed_at: ...
  collected_at: ...
  collection_freshness_status: fresh
  business_recency_status: current
  freshness_policy:
    cadence: daily
    stale_after_seconds: 129600
    expired_after_seconds: 345600
```

## DoD

- SQLite 可保存或稳定输出 `observed_at` 与 `collected_at`。
- 历史窗口查询不破坏现有 `ts` 时序逻辑。
- Data Quality 查询能获取 freshness policy 与两类 freshness 状态。
- P1-C22 报告使用 repository 输出字段，而不是临时猜测。
- 迁移或 metadata 方案都有测试覆盖。
- 旧数据兼容：没有 `collected_at` 的历史数据可通过 run/source health 进行合理推导，不能导致查询崩溃。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode mock
..\.venv\Scripts\python.exe -m onlybtc.cli metric-window dxy_proxy
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit --no-collect-live
..\.venv\Scripts\python.exe -m pytest
```

## 本次执行结果

已完成：

- `MetricValue.ts` 继续作为业务观测时间 `observed_at` 使用。
- `MetricValue.updated_at / created_at` 作为采集落库时间 `collected_at` 输出。
- `historical_window()` 输出：
  - `observed_at`
  - `collected_at`
  - `collection_freshness_status`
  - `business_recency_status`
  - `freshness_policy`
- P1-C22 指标参数清单已拆分采集新鲜度与业务时间新鲜度。

验证：

```text
ruff: All checks passed
pytest: 42 passed
P1-C22: collection freshness fresh=53, stale=0, expired=0, missing=0
```
