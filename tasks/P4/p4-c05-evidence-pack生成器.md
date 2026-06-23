# P4-C05 Evidence Pack 生成器

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.


## 状态

DONE

## 所属 Phase

P4

## 任务目标

围绕《开发文档.md》中对应 Phase 的设计，完成本任务所描述的能力建设，并保证产物可以被后续 Phase 复用。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 明确本任务涉及的数据结构、接口、组件、任务或配置。
- 遵守 evidence + data、历史窗口、数据质量、反证机制和预警边界。
- 不输出交易建议，不引入开仓、止损、仓位或杠杆逻辑。

## 输入

- 上游 Phase 或前置任务产物。
- 开发文档中对应模块、雷达、总控、预警或 Dashboard 规范。

## 输出

- 可运行或可复用的代码、配置、Schema、接口、组件或文档。
- 必要的测试、验证记录或运行说明。

## 验收标准

- 与《开发文档.md》的总体架构一致。
- 任务产物能被后续任务引用。
- 关键状态、错误和数据质量可观测。
- 不绕过状态机、反方审查、预警等级或数据质量约束。

## 依赖任务

TBD

## 备注

TBD

## 2026-05-21 全链条对齐补充

本卡必须对齐 P4-C12。Evidence Pack 必须冻结同一 run 的真实证据：

- 输入包括 P1 data quality、P2 radar outputs、P3 alerts、P3 invalidations、P3 anomaly/divergence/event rows。
- 写入 `evidence_packs`、`evidence_items`、`evidence_metric_links`。
- 每个 evidence item 必须带 `module_id`、direction、strength、data payload。
- 需要保存 source / metric / run refs，避免 P4 读取运行后变化的最新数据。
- Evidence Pack 是 P4-C06/C07/C08/C09 的唯一证据输入。

## 2026-05-21 P4-C13 全量 Radar 消费补充

Evidence Pack 不能只冻结 P2 Radar 的顶层结论，必须冻结并消费完整 Radar 数据：

- `radar_outputs`：14 个 Radar module 的 `signal / strength / confidence / data_quality / evidence_summary / conflicting_evidence / risk_flags / invalidation_signals`。
- `module_json_outputs.features[]`：每个 feature 的 `metric_id / role / evidence_tier / value / source_id / source_run_id / feature_run_scope / fallback_reason / quality_score`。
- `affects_signal / affects_confidence / affects_risk_flags` 必须进入 evidence item，用于区分主信号、上下文、风险、质量和审计证据。
- `provider_required / missing / suppressed` 不得丢弃，必须作为 coverage 和质量约束进入 Evidence Pack。
- P3-C14 新增的 `cpi_signed_days / fomc_signed_days / pce_signed_days / nfp_signed_days` 必须进入 event evidence。
- P3 `p3_event_window_engine` 的 `event_summary / daily_watch / signed_days / event_phase / publish_impact / source_trace` 必须进入 Evidence Pack。

P4-C05 DoD 追加：

- `radar_modules_consumed_count=14`。
- `signed_event_metrics_consumed_count=4`。
- `uncovered_metric_count=0`。
- `event_policy` 的 event_context 指标只影响风险与发布约束，不直接制造方向结论。

## 2026-05-21 分析师历史记忆优化

本节已补充独立任务卡：[P4-C14](p4-c14-llm分析师历史记忆sqlite持久化与本轮调用契约.md)。

为避免 4 个 LLM 分析师每次运行都“断层思考”，Evidence Pack 必须为每个分析师加入自己的历史记忆：

- 每个分析师生成 1 条 `analyst_history` evidence item。
- 从 `llm_model_votes` 读取该分析师最近 `history_limit` 次 vote。
- 同步携带 `debate_id / run_id / vote / confidence / evidence_ids / changed / final_state / consensus_score / disagreement_level`。
- 如果没有历史记录，也必须生成 cold-start history evidence，明确 `history_available=false`，让 prompt 知道这是首次判断。
- 这些历史 evidence 只能用于延续分析脉络、识别观点变化与置信度漂移，不能覆盖本轮 P2/P3 数据证据。

## 2026-05-21 Agent 化重构补充

P4-C05 生成的 Evidence Pack 是 Agent 化 P4 的唯一事实来源。后续需要在本卡或 P4-C01/P4-C06 中复用它生成 4 个 analyst input slice：

- 每个 slice 只包含该 analyst 负责的 Radar module evidence、P3 相关 evidence、必要 global constraints 和自己的 `analyst_history`。
- Evidence Pack 本体保持全量冻结，不因切片丢失证据。
- 任何 Agent 输入都不得绕过 Evidence Pack 直接查最新数据库。
- slice 生成结果需要进入 P4-C16 审计 HTML 的 coverage matrix。

## 2026-05-21 执行结果

已完成第一版 P4 Evidence Pack 生成器：

- 新增 `onlybtc.p4.evidence_pack.build_p4_evidence_pack()`。
- 新增 CLI：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-build-evidence-pack
```

真实库执行结果：

- `pack_id=p4-pack-20260521074431-c5e25a`
- `radar_run_id=p3-20260521072600-d38029`
- `p3_run_id=p3-20260521072600-d38029`
- `evidence_item_count=126`
- `radar_feature_evidence_count=118`
- `p3_event_evidence_count=4`
- `analyst_history_evidence_count=4`
- `radar_modules_consumed_count=14/14`
- `signed_event_metrics_consumed_count=4/4`

复跑 coverage audit：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-radar-coverage --pack-id p4-pack-20260521074431-c5e25a
```

结果：

- `evidence_pack_status=found`
- `evidence_pack_missing_feature_count=0`
- `uncovered_metric_count=0`

验证：

- `pytest backend/tests/test_p4_evidence_pack.py backend/tests/test_p4_radar_coverage.py -q` 通过。
- `ruff check backend/src/onlybtc/p4/evidence_pack.py backend/src/onlybtc/audit/p4_radar_coverage.py backend/src/onlybtc/cli.py backend/tests/test_p4_evidence_pack.py` 通过。
