# P1-C33 OFR 与 Glassnode 页面源 Freshness 策略修复

## 状态

DONE

## 所属 Phase

P1 数据源与历史数据底座

## 问题背景

本轮真实采集中，Data Quality 出现：

```text
ofr-fsi: expired
playwright-glassnode-asset-overview: stale
playwright-glassnode-sopr: stale
```

逐项检查后发现：

### OFR FSI

`https://www.financialresearch.gov/financial-stress-index/data/fsi.json` 可以正常访问，最新数据点为：

```text
2026-05-18 00:00 UTC, value = -2.604
```

当前系统把 `ofr-fsi` 当作 intraday 源，`expected_update_seconds=600`，这会把官方日频/可能滞后发布的数据误判为过期。

### Glassnode 页面源

Glassnode 页面抓取成功，接口返回 200，且最新数据点大多是 2026-05-20 UTC：

```text
playwright-glassnode-asset-overview: healthy, sample_count 正常
playwright-glassnode-sopr: healthy, sample_count 正常
```

但 Data Quality 中出现 stale，说明需要区分：

- 采集时间新鲜度：本轮是否真的刷新过页面
- 业务数据新鲜度：Glassnode 指标本身通常日频更新，落后数小时到 1 天是正常的

## 解决方案

### 1. OFR FSI 改成官方日频策略

为 `ofr-fsi` 配置显式 freshness policy：

```yaml
ofr-fsi:
  cadence: official_daily
  expected_update_seconds: 86400
  collection_stale_after_seconds: 129600
  collection_expired_after_seconds: 345600
  business_lagging_after_seconds: 259200
  business_outdated_after_seconds: 604800
  business_calendar: us_business_day
```

含义：

- 采集应每天刷新。
- 源数据 1-3 个美国工作日滞后属于正常范围。
- 超过 7 天才应视为业务过旧。

### 2. Glassnode 页面源拆分 freshness 语义

为 Glassnode 页面源配置：

```yaml
glassnode_public_page:
  cadence: page_snapshot_daily
  expected_update_seconds: 3600
  collection_stale_after_seconds: 7200
  collection_expired_after_seconds: 43200
  business_lagging_after_seconds: 172800
  business_outdated_after_seconds: 604800
  business_calendar: 24x7_daily_metric
```

同时 raw payload 增加：

```yaml
capture_diagnostics:
  browser_refreshed_at:
  proxy_token_obtained: true/false
  endpoint_status_by_metric:
  latest_point_by_metric:
```

### 3. Data Quality 展示修正

Data Quality 中把两个状态分开展示：

```text
collection_freshness: stale/expired
business_recency: current/lagging/outdated
```

Radar quality 主要按业务数据新鲜度扣分；页面采集 stale 只影响 source health，不直接把业务指标判死。

## DoD

- OFR FSI 不再按 10 分钟 intraday 判 expired。
- Glassnode 页面源成功刷新时，collection freshness 反映本轮采集状态。
- Glassnode 日频指标 24-48 小时内不被误判为业务过旧。
- P1-C22 问题清单中 OFR/Glassnode stale 数量下降，或者能明确解释为真实源滞后。
- onchain_valuation 的质量分不再因为页面源 freshness 误判而被过度扣分。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode live --source-id ofr-fsi
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode live --source-id playwright-glassnode-asset-overview --source-id playwright-glassnode-sopr
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit --no-collect-live
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check src tests
```
