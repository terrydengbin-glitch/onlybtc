# P1-C26 数据源真实更新频率与 Freshness Policy

## 状态

DONE

## 来源

P1-C22 复跑后仍有：

```text
freshness: stale=5, expired=35
```

根因之一是所有数据源共用过于简单的 freshness 阈值。不同数据源的真实更新频率差异很大，不能用同一套分钟级规则判断。

## 所属 Phase

P1 数据源与历史数据底座 / P2 Radar / P5 Data Quality

## 当前问题

当前 freshness 判断缺少源级和指标级 policy：

- Binance / Bybit：秒级或分钟级更新。
- FRED：日更、周更、月更混合。
- CoinMetrics Community：日更。
- OFR FSI：通常日更或工作日更新。
- Fed RSS / Calendar：事件型更新。
- Bitbo / Glassnode / Clark Moody 页面：页面刷新型，部分指标 15 分钟、1 小时或日更。

如果统一按 10 分钟 stale、60 分钟 expired，会误伤大量宏观与链上低频指标。

## 目标

为 source / metric 建立真实更新频率配置：

```yaml
freshness_policy:
  source_id: fred-macro
  default_cadence: daily
  stale_after: 36h
  expired_after: 96h
  business_calendar: us_market_days

  metric_overrides:
    fed_balance_sheet:
      cadence: weekly
      stale_after: 10d
      expired_after: 21d
```

## 修复要求

### 1. Source 级 policy

`SOURCE_CONFIGS` 或 provider registry 增加：

```yaml
data_cadence:
  kind: realtime | intraday | daily | weekly | monthly | event | page_snapshot
  expected_update_seconds: 600
  stale_after_seconds: 1800
  expired_after_seconds: 7200
```

### 2. Metric 级 override

允许同一 source 内不同指标有不同更新节奏：

```yaml
metric_freshness_overrides:
  fed_balance_sheet:
    cadence: weekly
    stale_after_seconds: 864000
    expired_after_seconds: 1814400
```

### 3. 业务日历

支持简单业务日历语义：

- `24x7`
- `us_business_day`
- `fed_release_schedule`
- `event_time`

避免周末、节假日、FOMC 日历类数据被错误判过期。

## 建议默认策略

```yaml
policy_defaults:
  realtime:
    stale_after: 5m
    expired_after: 30m
  intraday:
    stale_after: 30m
    expired_after: 3h
  daily:
    stale_after: 36h
    expired_after: 96h
  weekly:
    stale_after: 10d
    expired_after: 21d
  monthly:
    stale_after: 45d
    expired_after: 75d
  event:
    stale_after: until_event_passed
    expired_after: after_event_window
```

## DoD

- `freshness_policy` 可从 source config 读取。
- `metric_id` 可以覆盖 source 默认 freshness。
- `write_data_quality_snapshot()` 按 policy 判断数据新鲜度。
- P1-C22 报告展示每个指标的 `source_update_frequency`、`stale_after`、`expired_after`。
- FRED / CoinMetrics / Fed / OFR 类低频数据在正常更新时间内不再被标为 expired。
- 测试覆盖：
  - 日更数据不会被 10 分钟规则误伤。
  - 实时数据超过阈值仍会过期。
  - metric override 优先于 source 默认 policy。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit
..\.venv\Scripts\python.exe -m pytest
```

## 本次执行结果

已完成：

- 新增 freshness policy 推导：
  - `intraday`
  - `daily`
  - `weekly`
  - `event`
  - `page_snapshot`
- FRED 默认按日更/周更评估业务时间。
- Fed RSS / Calendar 按事件型数据评估。
- Playwright 页面按页面快照型数据评估。
- mempool Lightning 明确按 intraday 数据处理。
- P1-C22 报告新增 `freshness_policy` 列。

验证：

```text
P1-C22 Data Quality score: 0.9138
P1-C22 Data Quality status: healthy
```
