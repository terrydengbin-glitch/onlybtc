# P2-C20 Radar 指标覆盖补齐与全量采集指标纳入治理

## 状态

DONE

## 所属 Phase

P2 全量雷达模块 / P1 数据源与历史数据 / P3 算法敏感检测 / P4 Evidence Pack

## 背景

P4 全链条复盘时发现，如果 P4 只消费 P2 Radar，会遗漏部分 P1 已采集指标。回到 P2 审计后确认：

```text
METRIC_DEFINITIONS: 107
P2 Radar 涉及指标位: 83
实际覆盖 METRIC_DEFINITIONS: 79
未进入 Radar 的采集指标: 28
Radar 引用但尚无 MetricDefinition 的 provider_required / planned 指标: 4
```

这不是 P4 应该兜底的问题。P2 Radar 必须尽量纳入所有已采集指标，并区分：

- 主信号指标：直接影响 signal / strength。
- 辅助上下文指标：影响 confidence、risk_flags、evidence_summary。
- 质量/事件上下文指标：影响 invalidation_signals、risk_flags、event windows。

## 未进入 Radar 的 28 个指标归类方案

| metric_id | 建议 Radar | 角色 | 建议处理 |
|---|---|---|---|
| `btc_1h_open` | `kline_orderflow` | supporting_context | 纳入 K 线结构，辅助判断实体/缺口，不直接强权重 |
| `btc_1h_high` | `kline_orderflow` | primary/supporting | 计算 1h range / 上影压力 |
| `btc_1h_low` | `kline_orderflow` | primary/supporting | 计算 1h range / 下影支撑 |
| `btc_block_height` | `btc_total_state` | audit_context | 区块链进度与减半数据一致性校验 |
| `btc_halving_blocks_remaining` | `btc_total_state` / `event_policy` | event_context | 与 `btc_halving_estimated_days` 一起进入减半事件上下文 |
| `cap_real_usd` | `onchain_valuation` | supporting_context | realized cap 与 realized price / supply 交叉校验 |
| `supply_current` | `onchain_valuation` | audit_context | 估值分母校验，不直接产生方向 |
| `aggregate_macro_surprise` | `event_policy` / `macro_radar` | primary/supporting | 宏观 surprise 汇总，应进入事件政策风险 |
| `macro_surprise_event_count` | `event_policy` | quality_context | 判断 surprise score 可信度，低事件数降 confidence |
| `next_fed_speech_hours_until` | `event_policy` | event_context | Fed speech 事件窗口 |
| `fed_speaker_weight` | `event_policy` | primary/supporting | Fed 发言重要度 |
| `fed_speech_hawkish_score` | `event_policy` | primary | 鹰派风险 |
| `fed_speech_dovish_score` | `event_policy` | primary | 鸽派缓和 |
| `fomc_blackout_active` | `event_policy` | event/risk_context | blackout 风险锁定，限制解释强度 |
| `hashrate_90d_ehs` | `btc_adoption` | supporting_context | 与 `btc_hashrate` 做趋势确认 |
| `hash_price_usd` | `btc_adoption` / `onchain_valuation` | risk_context | 矿工收入压力，影响链上基本面风险 |
| `avg_fees_per_block_btc` | `trade_structure_flow` / `btc_adoption` | supporting_context | 链上费用需求 |
| `fees_vs_reward_pct` | `trade_structure_flow` / `btc_adoption` | risk_context | 手续费/区块奖励结构 |
| `lightning_capacity_usd` | `btc_adoption` | supporting_context | Lightning 容量 USD 口径 |
| `lightning_channel_count` | `btc_adoption` | primary/supporting | 网络采用率 |
| `lightning_tor_capacity_btc` | `btc_adoption` | risk_context | Tor 网络结构占比 |
| `lightning_tor_capacity_pct` | `btc_adoption` | risk_context | Tor 容量占比 |
| `lightning_tor_node_count` | `btc_adoption` | risk_context | Tor 节点结构 |
| `bitcoin_tor_nodes` | `btc_adoption` | risk_context | Bitcoin 节点可达性结构 |
| `bitcoin_tor_nodes_pct` | `btc_adoption` | risk_context | Tor 节点占比 |
| `mempool_tx_count` | `trade_structure_flow` | primary/supporting | mempool 拥堵 |
| `mempool_vsize_mb` | `trade_structure_flow` | primary/supporting | mempool 拥堵规模 |
| `mempool_pending_fees_btc` | `trade_structure_flow` | supporting/risk | 链上待确认手续费压力 |

## Radar 引用但尚无 MetricDefinition 的 4 个指标

| metric_id | 当前 Radar | 处理建议 |
|---|---|---|
| `whale_flow` | `onchain_valuation` | 保留 provider_required，不应计入主覆盖缺口 |
| `miner_flow` | `onchain_valuation` | 保留 provider_required，不应计入主覆盖缺口 |
| `hibor` | `asia_risk` | 若短期无数据源，应标记 planned/provider_required 或补 MetricDefinition |
| `regulatory_event_score` | `event_policy` | 若短期无数据源，应标记 planned/provider_required 或补 MetricDefinition |

## 修复目标

P2 Radar 不只是覆盖“主指标”，还要覆盖所有已采集指标的业务位置：

```text
P1 metric_values
  -> P2 RadarMetricRule / context rule
  -> radar_outputs + module_json_outputs
  -> P3 feature/anomaly/invalidation
  -> P4 Evidence Pack
```

## 实施要求

### 1. Radar registry 扩展

将 28 个缺口指标纳入对应 Radar。权重策略：

- 主信号指标给实际权重。
- 上下文/审计指标可设置低权重或 `change_sensitive=False`。
- 中性上下文指标不可制造方向，但必须进入 features/evidence_summary。

### 2. Radar 分析逻辑优化

当前 `RadarMetricRule` 只有简单 `metric_id / weight / higher_is / change_sensitive`，不足以表达上下文指标。需要新增或等价实现：

```yaml
role: primary_signal | supporting_context | risk_context | audit_context | quality_context | event_context
affects_signal: true/false
affects_confidence: true/false
affects_risk_flags: true/false
```

要求：

- audit/context 指标不应扭曲 signal。
- quality_context 指标可影响 confidence / invalidation。
- event_context 指标进入 risk_flags / evidence_summary。
- provider_required 不应强制 medium quality。

### 3. P2 审计报告扩展

`reports/p2-radar-quality-report.html` 必须新增覆盖检查：

- `metric_definitions_count`
- `radar_covered_metric_count`
- `uncovered_metric_count`
- uncovered metric table
- provider_required/planned metric table

目标：

```text
uncovered_metric_count = 0
```

### 4. P3/P4 下游影响

补齐后必须复跑：

- P2 full audit
- P3 full audit

确认：

- P3 feature rows 增加或保持合理。
- P3 anomaly 不因上下文指标异常膨胀。
- P4-C12 的 analyst coverage matrix 可以直接从 P2/P3 读取。

## DoD

- 28 个未进入 Radar 的采集指标全部归入 Radar。
- 4 个 Radar 引用但未定义指标被明确标记 provider_required/planned 或补定义。
- P2 HTML 显示覆盖率，`uncovered_metric_count=0`。
- audit/context 指标不会错误改变主信号。
- `pytest backend/tests -q` 与 ruff 通过。
- 复跑 `scripts/p2-full-audit.ps1 -NoCollectLive` 与 `scripts/p3-full-audit.ps1 -NoCollectLive`。
- 同步 P4-C12 说明：P4 不再兜底 P2 未覆盖指标，而是消费 P2/P3 已归位证据。

## 执行记录

2026-05-21 已完成：

- `RadarMetricRule` 新增 `role / affects_signal / affects_confidence / affects_risk_flags` 语义。
- 28 个未进入 Radar 的采集指标已全部归入现有 Radar。
- `whale_flow / miner_flow / hibor / regulatory_event_score` 保留为 provider_required/planned，不计入已采集指标缺口。
- P2 HTML 新增 Metric Coverage、Uncovered Metric Definitions、Radar Planned / Provider Required 表。
- 覆盖检查结果：`METRIC_DEFINITIONS=107`，`radar_metric_slot_count=114`，`radar_unique_metric_count=111`，`uncovered_metric_count=0`。
- P2 审计结果：`p2_radar_run_id=radar-20260521061229-d75256`，`feature_values=114`，`provider_required_count=4`，`low_quality_modules=[]`。
- P3 复跑结果：`p2_radar_run_id=radar-20260521061229-dd949d`，`p3_run_id=p3-20260521061230-9e91c8`，`feature_rows_written=963`。
- 验证：`pytest backend/tests -q` 通过，71 passed；ruff 通过。

2026-05-21 P3-C14 追加同步：

- 新增 `cpi_signed_days / fomc_signed_days / pce_signed_days / nfp_signed_days`，`METRIC_DEFINITIONS` 当前为 111。
- P2 `event_policy` 已将 4 个 signed days 作为 `event_context` 纳入 Radar 覆盖，只进入证据与风险上下文，不影响方向信号。
- 最新验证：`pytest backend/tests -q` 通过，74 passed；ruff 通过。
