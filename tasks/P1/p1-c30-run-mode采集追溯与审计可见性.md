# P1-C30 run_mode 采集追溯与审计可见性

## 状态

DONE

## 执行记录

- `collect_sources(mode=...)` 已贯穿写入 `source_runs.mode`、`raw_observations.mode`、`metric_values.run_mode`。
- Data Quality 快照已补充 `run_mode_summary`、`fallback_summary`，`stale_sources` 可携带 `source_id`。
- P1-C22 审计已展示 Run Mode 混用风险、Fallback/Warning/403 情况，并继续输出中文 HTML。
- P1-C22 在 `--no-collect-live` 下已默认选择最新 `mode=live` 的采集 run，避免误取最新 mock 快照。
- 本轮 live 采集成功：`collected=63`、`errors=0`、`data_quality.status=healthy`。
- 当前保留的非阻断问题：BLS 403、FXStreet 本轮无可用 USD actual/consensus、mempool Lightning API warning，已进入 warnings/fallback 审计链路。

## 所属 Phase

P1 数据源与历史数据底座

## 上游依赖

- P8-C16：SQLite 已支持 `run_mode` / `mode` 字段与 live-only 历史窗口过滤。

## 问题背景

真实采集链路可以跑通，但当前审计仍有两个可见性缺口：

1. 采集结果无法清晰区分 `live/mock/test`，导致真实算法可能混入测试样本。
2. BLS 请求出现 `403`，但 `collect-sources` 的顶层 `errors=[]`，说明 fallback 或默认数据可能生效，但审计报告没有把 fallback 使用情况暴露出来。
3. Data Quality 的 `stale_sources` 目前缺少 `source_id`，UI 不好定位是哪一个源 stale。

## 任务目标

让 P1 采集结果、数据质量快照和 P1-C22 审计报告都能清楚回答：

```text
这条数据是 live / mock / test？
是否用了 fallback？
是否有页面 403 / parser fallback / default fallback？
哪些 source stale / lagging？
当前是否存在 live/mock 混用风险？
```

## 需要修改

### 1. 采集链路写入 mode

`collect_sources(mode=...)` 持久化时写入：

```yaml
source_runs.mode: live/mock/test
raw_observations.mode: live/mock/test
metric_values.run_mode: live/mock/test
```

要求：

- live 采集必须标记 `live`。
- mock 采集必须标记 `mock`。
- 测试手工插入可标记 `test`，未标记旧数据为 `unknown`。

### 2. Data Quality 补充 source_id

`write_data_quality_snapshot()` 的以下列表必须包含 `source_id`：

```yaml
stale_sources:
  - source_id
  - freshness_status
  - collection_age_seconds
  - business_recency_status
  - last_collected_at
  - last_observed_at

business_lagging_sources:
  - source_id
  - ...
```

### 3. fallback / warning 可见性

当某个 source 出现：

- HTTP 403
- parser 失败
- 使用 fallback source
- 使用默认/估算数据
- page snapshot partial

必须进入：

```yaml
source_health_events.message
fallback_events
data_quality_snapshot.payload.fallback_summary
p1-c22 HTML
```

### 4. P1-C22 审计增强

P1-C22 中文 HTML 增加章节：

```text
Run Mode 混用风险
Fallback / 默认数据使用清单
Stale Source 定位清单
```

输出字段：

```yaml
run_mode_summary:
  live_metric_values
  mock_metric_values
  test_metric_values
  unknown_metric_values
  mixed_metric_ids
  production_blocker: true/false

fallback_summary:
  fallback_event_count
  warning_source_count
  http_403_sources
  default_value_sources
```

## DoD

- live 采集后新增数据全部带 `run_mode=live`。
- mock 采集后新增数据全部带 `run_mode=mock`。
- P1-C22 能明确提示 live/mock/test/unknown 混用风险。
- `stale_sources` 可直接被 UI 展示 source_id。
- BLS 403 这类 fallback/partial 情况不再被顶层 `errors=[]` 掩盖。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode live
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit --no-collect-live
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check src tests
```
