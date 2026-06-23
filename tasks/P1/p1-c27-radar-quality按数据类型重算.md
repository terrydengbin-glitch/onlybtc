# P1-C27 Radar Quality 按数据类型重算

## 状态

DONE

## 来源

P1-C22 复跑后仍发现部分 Radar quality 偏低：

```text
low / medium modules:
- macro_radar
- dollar_liquidity
- treasury_credit
- fund_flow
- btc_adoption
- onchain_valuation
- asia_risk
```

当前偏低主要不是因为采集失败，而是 freshness 误伤传导到 Radar 层。

## 所属 Phase

P1 数据质量 / P2 Radar / P5 Dashboard 与 Data Quality

## 当前问题

Radar quality 当前过度依赖统一 freshness：

```text
business timestamp old -> metric expired -> module quality down
```

但宏观、链上估值、Fed 日历等模块天然不是分钟级数据。如果采集刚刚成功，且业务时间符合该源更新频率，Radar 不应该被判为低质量。

## 目标

将 Radar quality 拆成可解释的质量组成：

```yaml
radar_quality:
  overall_score: 0.82
  coverage_score: 0.95
  collection_freshness_score: 0.92
  business_recency_score: 0.80
  source_quality_score: 0.86
  conflict_penalty: -0.04
  proxy_penalty: -0.05
  page_source_penalty: -0.03
```

## 修复要求

### 1. 输入质量分层

Radar 消费指标时，需要读取：

- `collection_freshness`
- `business_recency`
- `source_quality`
- `source_type`
- `source_form`
- `exact_or_proxy`
- `conflict_status`

### 2. 按模块调整权重

不同雷达模块使用不同质量权重：

```yaml
macro_radar:
  business_recency_weight: medium
  collection_freshness_weight: high

derivatives_crowding:
  business_recency_weight: high
  collection_freshness_weight: high

event_policy:
  event_window_weight: high
  source_quality_weight: high
```

### 3. 质量解释写入 Radar output

每个 Radar output 需要包含：

```yaml
quality_explanation:
  score: 0.82
  main_discount_reasons:
    - source_conflict: lightning_channel_count
    - proxy_metric: exchange_balance_delta_1d_proxy
  not_discounted:
    - fred_daily_data_is_within_expected_cadence
```

## DoD

- Radar quality 不再把符合真实更新频率的数据误判为低质量。
- Radar output 包含质量拆解和扣分原因。
- P5 Dashboard / Radar Detail / Data Quality 可展示质量解释。
- P1-C22 报告中 Radar quality 偏低时能指出具体原因。
- 测试覆盖：
  - 日更宏观数据在 policy 内不扣 collection freshness。
  - 高频衍生品数据超时会扣分。
  - 多源冲突会独立扣分，但不等同于采集失败。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli analyze-radars
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit --no-collect-live
..\.venv\Scripts\python.exe -m pytest
```

## 本次执行结果

已完成：

- Radar quality 拆成：
  - `coverage_score`
  - `collection_freshness_score`
  - `business_recency_score`
  - `source_quality_score`
  - `conflict_penalty`
- Radar output 的 `evidence_summary` 写入 `quality_explanation`。
- Radar invalidation signals 新增 `business_lagging_metrics`。
- 低频宏观、链上、事件类数据不再因业务时间戳低频被误判为低质量。

复跑 P1-C22：

```text
多数 Radar quality 已恢复为 high。
onchain_valuation 仍为 medium，原因是 whale_flow / miner_flow 等链上流量指标仍属于后续数据源缺口或代理指标问题，不是 freshness bug。
```
