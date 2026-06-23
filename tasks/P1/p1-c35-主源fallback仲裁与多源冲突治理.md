# P1-C35 主源、Fallback 仲裁与多源冲突治理

## 状态

DONE

## 所属 Phase

P1 数据源与历史数据底座 / P2 Radar Quality / P5 Evidence 与 Radar Detail

## 问题背景

全量 `P1-C22` live 审计已无采集失败，但仍显示：

```text
多源冲突：13 个指标存在多源数值冲突
```

代码链路为：

```text
metric_values 多源历史
  -> historical_window(metric_id)
  -> _window_arbitration_key()
  -> _source_conflict()
  -> Radar conflicting_evidence / P1-C22 conflict_status
```

当前问题不是“多源都坏了”，而是缺少明确的主源、fallback、cross-check 语义：

- 部分 fallback 源被当作同等候选并触发冲突。
- 部分同名指标其实口径不同，应该拆成不同 metric 或标记为 definition_conflict。
- 部分事件源是不同事件流，不应互相当作同一指标冲突。
- 部分实时页面源与官方滞后源同时存在时，应按主源优先级与业务时间状态决策。

## 当前冲突分组

### 1. 实时源 vs 官方滞后源

| metric_id | selected | conflicting | 当前冲突 | 根因 |
|---|---|---|---|---|
| dxy_proxy | fred-dxy | playwright-tradingview-dxy | high / update_lag | FRED 代理滞后，实时页面源更贴近当前 |
| jgb_10y | fred-jgb-10y | playwright-tradingview-jgb-10y | high / update_lag | FRED JGB 过旧，页面源当前但需要数值校验 |

### 2. 页面实时源 vs FRED fallback

| metric_id | selected | fallback | 当前冲突 | 根因 |
|---|---|---|---|---|
| wti_oil | playwright-tradingview-wti-oil | fred-wti-oil | high | 当前期货/现货或合约口径不同 |
| brent_oil | playwright-tradingview-brent-oil | fred-brent-oil | high | 同上 |

### 3. 同名指标但定义不同

| metric_id | selected | conflicting | 当前冲突 | 根因 |
|---|---|---|---|---|
| active_addresses | blockchain-active-addresses | playwright-glassnode-asset-overview | high | Blockchain.com 与 Glassnode active address 口径不同 |
| lightning_capacity_btc | mempool-lightning-network-stats | clarkmoody-dashboard | low | 统计窗口/公开网络定义不同 |
| lightning_channel_count | mempool-lightning-network-stats | clarkmoody-dashboard | high | 定义或采样范围不同 |
| lightning_node_count | mempool-lightning-network-stats | clarkmoody-dashboard | high | 定义或采样范围不同 |

### 4. 不同事件流不应互相冲突

| metric_id | selected | conflicting | 当前冲突 | 根因 |
|---|---|---|---|---|
| fed_speaker_weight | fed-rss-all-speeches | fed-rss-all-testimony | high / update_lag | speeches 与 testimony 是不同事件流 |
| fed_speech_hawkish_score | fed-rss-all-speeches | fed-rss-all-testimony | high / update_lag | 同上 |
| fed_speech_dovish_score | fed-rss-all-speeches | fed-rss-all-testimony | high / update_lag | 同上 |
| fed_speech_content_risk | fed-rss-all-speeches | fed-rss-all-testimony | high / update_lag | 同上 |
| fed_speech_risk | fed-rss-all-speeches | fed-rss-all-testimony | high / update_lag | 同上 |

## 目标

建立显式的多源治理规则：

```yaml
metric_source_policy:
  metric_id:
    primary_source:
    fallback_sources:
    cross_check_sources:
    conflict_policy:
      mode: suppress_fallback | warn | split_definition | event_stream_aggregate
      threshold:
      user_visible:
      affects_radar_quality:
```

核心原则：

- 主源可用时，fallback 不应默认触发高优先级冲突。
- 口径不同的同名指标应拆名或标记 definition，不进入强冲突扣分。
- 不同事件流应聚合或拆分，不作为同一指标冲突。
- 真正的同源口径冲突仍要进入 Evidence / Radar Detail。

## 修复要求

### 1. 主源 / fallback / cross-check registry

在 `sources.service` 或独立配置中沉淀 metric-level policy，替代零散的 `_METRIC_SOURCE_OVERRIDES`。

必须覆盖：

- DXY：TradingView 当前值为 primary 或至少 current primary；FRED 为 daily fallback/cross-check。
- WTI / Brent：TradingView 为 primary，FRED 为 daily fallback，冲突按口径说明展示，不扣强分。
- JGB：TradingView 为 primary，但必须加 value_min/value_max 校验，FRED 为 stale fallback。
- Lightning：mempool 为 primary，Clark Moody 为 cross-check，定义差异不算强冲突。
- Fed speeches/testimony：拆分事件流或聚合为 `fed_policy_communication_risk`，不互相冲突。
- Active addresses：Blockchain 与 Glassnode 拆成不同 metric，或显式选择一个为 adoption 主源。

### 2. 仲裁排序修正

当前 `historical_window()` 的候选排序需要明确：

```text
collection freshness
business recency
source role
metric-level priority
effective quality
value validation
```

不能只靠 `quality + freshness + priority` 让滞后的官方源压过实时源。

### 3. Conflict 类型扩展

当前 `_source_conflict()` 只有粗略：

```text
definition_conflict / update_lag / value_conflict
```

需要扩展：

```text
fallback_difference
definition_difference
event_stream_difference
invalid_candidate_value
true_value_conflict
```

只有 `true_value_conflict` 默认影响 Radar quality。

### 4. Evidence / Radar Detail 输出

保留冲突可见性，但改成解释型：

```yaml
selected_source:
fallback_sources:
cross_checks:
suppressed_conflicts:
true_conflicts:
definition_notes:
```

前端 P5-C24 可直接消费。

## DoD

- 全量 `P1-C22` 后，多源冲突数量显著下降，只保留真实同口径冲突。
- fallback 与 primary 数值不同不会默认产生 high conflict。
- Fed speeches/testimony 不再互相作为同一指标冲突。
- active_addresses、Lightning 指标冲突有明确口径解释。
- Radar quality 不再被 suppressed conflict 过度扣分。
- P1-C22 指标清单中展示主源、fallback、cross-check 和冲突处理结论。
- 测试覆盖 primary 可用、primary 失效 fallback 接管、definition difference、event stream difference、invalid candidate value。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check src tests
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit
```
