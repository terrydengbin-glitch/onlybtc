# P4-C13 P4 全量 Radar Evidence Pack 消费与新增事件指标契约

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## 所属 Phase

P4 LLM 推理与总控融合 / P2 全量 Radar / P3 事件窗口分析器 / P8 Evidence Pack

## 背景

P2-C20 后，P2 Radar 已不再只覆盖主信号指标，而是覆盖全部采集指标，并通过 `role / affects_signal / affects_confidence / affects_risk_flags` 区分：

- `primary_signal`
- `supporting_context`
- `risk_context`
- `audit_context`
- `quality_context`
- `event_context`

P3-C14 后，又新增了：

- `cpi_signed_days`
- `fomc_signed_days`
- `pce_signed_days`
- `nfp_signed_days`

这些 signed days 已进入 P2 `event_policy` Radar 的 `event_context`，同时 P3 `p3_event_window_engine` 已输出：

- `signed_days`
- `event_phase`
- `window_action`
- `event_summary`
- `daily_watch`
- `source_trace`

因此 P4 必须升级 Evidence Pack 消费契约，不能只读取 Radar 的顶层 `signal / strength / confidence`，也不能只读少数 top evidence。

## 业务目标

P4 Evidence Pack 必须完整消费同一 run 的 P2/P3 结构化证据：

```text
P2 radar_outputs
  + P2 module_json_outputs.full_features
  + P2 role / risk_flags / invalidation_signals / conflicting_evidence
  + P3 event_summary / daily_watch / invalidation_events
  -> frozen evidence_pack
  -> four analyst inputs
  -> rule baseline / LLM debate / judge synthesis
```

P4 的核心原则：

- P4 只解释和融合 P2/P3 已归位证据，不回头兜底 P1 未归类指标。
- P4 必须让 4 个分析师合计覆盖全部 Radar features，而不是只消费模块 summary。
- `event_context / quality_context / audit_context` 必须进入证据和风险约束，但不能错误制造方向信号。
- P3-C14 的事件窗口摘要必须进入 P4 Evidence Pack 和 event-policy analyst 输入。

## 输入契约

P4-C13 要求 Evidence Pack 读取：

### P2 Radar 全量输入

- `radar_outputs`
  - `module_id`
  - `signal`
  - `strength`
  - `confidence`
  - `data_quality`
  - `evidence_summary`
  - `conflicting_evidence`
  - `risk_flags`
  - `invalidation_signals`
- `module_json_outputs`
  - `features[]`
  - 每个 feature 的 `metric_id / role / evidence_tier / value / source_id / source_run_id / feature_run_scope / fallback_reason / quality_score`
  - `affects_signal / affects_confidence / affects_risk_flags`

### P3 算法与事件窗口输入

- `feature_values`
  - `p3_anomaly_engine`
  - `p3_divergence_engine`
  - `p3_event_window_engine`
- P3-C14 事件字段：
  - `signed_days`
  - `event_phase`
  - `window_action`
  - `event_summary`
  - `daily_watch`
  - `source_trace`
  - `publish_impact`
- `invalidation_events`
  - `event_risk_details`
  - `reason_code`
  - `direction_scope`
  - `quality_impact`
  - `publish_impact`

### P1/P8 质量输入

- `data_quality_snapshots`
- `source_health_events`
- `source_runs`
- `raw_observations.payload_hash`
- `fallback_events`

## Evidence Pack 输出契约

每个 `evidence_item` 必须至少包含：

```yaml
evidence_id
controller_run_id
collect_run_id
p2_radar_run_id
p3_run_id
source_layer: p2_radar | p3_event | p3_anomaly | p3_divergence | p3_invalidation | p1_quality
module_id
metric_id
source_id
source_run_id
feature_run_scope
role
affects_signal
affects_confidence
affects_risk_flags
value
quality_score
signal_direction
confidence_impact
risk_impact
payload
```

事件窗口 evidence item 必须额外包含：

```yaml
event_type
signed_days
event_phase
window
window_action
event_summary
daily_watch
publish_impact
source_trace
```

## 四分析师消费规则

P4 的 4 个分析师必须按 Radar 模块和 source_layer 消费完整 evidence：

| 分析师 | 必须消费的模块 |
|---|---|
| Macro & Event Analyst | `macro_radar`, `treasury_credit`, `asia_risk`, `event_policy`, P3 event windows |
| Liquidity & Flow Analyst | `usd_liquidity`, `fund_flow`, `btc_adoption`, stablecoin / ETF / exchange flow |
| Leverage & Microstructure Analyst | `derivatives_crowding`, `trade_structure_flow`, `options_volatility`, liquidation / funding / OI |
| On-chain & Market Structure Analyst | `onchain_valuation`, `crypto_breadth`, `btc_total_state`, price/technical P3 features |

要求：

- 每个 Radar module 至少进入一个分析师输入。
- 每个 `module_json_outputs.features[]` 至少形成一个 evidence item 或被明确记录为 `provider_required / missing / suppressed`。
- `event_context / quality_context / audit_context` 不直接改变方向票，但必须进入 missing_evidence、confidence discount、publish constraints。
- `true_source_conflict` 必须进入所有相关分析师的 conflicting evidence。
- P3 `daily_watch.no_material_change` 也必须进入事件分析师的 evidence，表示已检查但无实质变化。

## P4 审计要求

`reports/p4-controller-audit-report.html` 必须新增：

- Radar full consumption summary
- Radar modules consumed count，目标 14/14
- Radar feature items consumed count
- Metrics covered by P2 Radar
- Metrics covered by P3-only evidence
- Uncovered metric count，目标 0
- Event window evidence table
- Signed days / event_phase / daily_watch / publish_impact
- Analyst coverage matrix

## DoD

- P4 Evidence Pack 能读取同一 run 的全部 `radar_outputs` 和 `module_json_outputs`。
- P4 Evidence Pack 覆盖所有 P2 Radar features，不只读取 top summary。
- 新增 4 个 signed days 已进入 P4 event evidence。
- P3-C14 `event_summary / daily_watch` 已进入 P4 Evidence Pack。
- 4 个分析师 coverage matrix 显示 14 个 Radar module 均被消费。
- P4 审计 HTML 显示 `uncovered_metric_count=0`。
- P4 输出不得绕过 P3 invalidation、event publish impact、run_mode integrity。
- 不输出交易建议、开仓、止损、仓位、杠杆。

## 2026-05-21 基线审计结果

已新增 P4 Radar coverage 审计入口：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-radar-coverage
```

输出：

- `reports/p4-radar-coverage-matrix.html`

当前真实库审计结果：

- `radar_run_id=p3-20260521072600-d38029`
- `p3_run_id=p3-20260521072600-d38029`
- `radar_modules_consumed_count=14/14`
- `radar_feature_items_available=118/118`
- `signed_event_metrics_consumed_count=4/4`
- `uncovered_metric_count=0`
- `evidence_pack_status=not_generated`
- `evidence_pack_missing_feature_count=118`

结论：

- 4 个分析师 coverage matrix 可以完整覆盖当前全部 Radar module 与 Radar features。
- P2/P3 上游没有 Radar 覆盖缺口。
- 真正缺口在 P4-C05：Evidence Pack 尚未把 118 个 Radar features 冻结为 `evidence_items`。

## 2026-05-21 后续同步

P4-C05 已补齐 Evidence Pack 生成器，并补充独立任务卡 [P4-C14](p4-c14-llm分析师历史记忆sqlite持久化与本轮调用契约.md)：

- 当前 `evidence_pack_missing_feature_count=0`。
- 每个 Evidence Pack 额外生成 4 条 `analyst_history` evidence。
- 分析师历史来自 SQLite `llm_model_votes / llm_debates`，并可被本轮 Evidence Pack 调用。

## 2026-05-21 验收收口

已重新执行真实库 P4 coverage 与 Evidence Pack 验收：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-radar-coverage
.\.venv\Scripts\python.exe -m onlybtc.cli p4-build-evidence-pack
.\.venv\Scripts\python.exe -m onlybtc.cli p4-radar-coverage --pack-id p4-pack-20260521082743-2bf998
```

最终结果：

- `pack_id=p4-pack-20260521082743-2bf998`
- `radar_modules_consumed_count=14/14`
- `radar_feature_items_available=118/118`
- `radar_feature_evidence_count=118`
- `p3_event_evidence_count=4`
- `analyst_history_evidence_count=4`
- `signed_event_metrics_consumed_count=4/4`
- `uncovered_metric_count=0`
- `evidence_pack_status=found`
- `evidence_pack_missing_feature_count=0`
- HTML：`reports/p4-radar-coverage-matrix.html`

P4-C13 验收通过，状态更新为 DONE。
