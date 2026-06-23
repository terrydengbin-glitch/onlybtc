# P4-C01 Analyst Agent 输入输出 Schema

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

本卡必须对齐 P4-C12。模块 LLM Schema 不再使用 PPT 式抽象输入，必须定义可校验的真实输入输出：

- 输入来自 `module_json_outputs`、`radar_outputs`、P3 anomaly/divergence/event/invalidation rows、`data_quality_snapshots`。
- 每条模型可解释结论必须引用 `evidence_id`、`module_id`、`metric_id`、`source_id`、`run_id`。
- 输入必须包含 P3-C12 字段：`reason_code`、`affected_metrics`、`direction_scope`、`quality_impact`、`publish_impact`。
- 输出只能是模块级解释，不允许输出最终 BTC 状态或交易建议。
- Schema 必须支持 JSON 校验与 mock response 测试。

## 2026-05-21 P4-C13 全量 Radar Schema 补充

模块 LLM 输入 Schema 必须支持 P4-C13 的全量 Radar Evidence Pack：

- 每个 analyst input 必须包含所负责 Radar modules 的完整 `features[]`，不能只包含 top summary。
- 每个 feature 必须携带 `role / affects_signal / affects_confidence / affects_risk_flags / feature_run_scope / fallback_reason`。
- P3-C14 event evidence 必须携带 `signed_days / event_phase / window_action / event_summary / daily_watch / publish_impact`。
- Schema 必须区分 `primary_signal` 与 `event_context / quality_context / audit_context`，禁止 LLM 把上下文指标当作方向主信号。
- 输出必须引用 `evidence_id`，不能引用未进入 Evidence Pack 的 Radar 或 metric。

## 2026-05-21 Agent 化重构补充

本卡从“模块 LLM Schema”升级为“Analyst Agent Schema”。P4 不再按 14 个 Radar module 分别调用 LLM，而是按 4 个业务分析师 Agent 消费 Evidence Pack slice。

| analyst_id | 负责范围 |
|---|---|
| `macro_event_analyst` | `macro_radar`、`treasury_credit`、`asia_risk`、`event_policy`、P3 event windows |
| `liquidity_flow_analyst` | `dollar_liquidity`、`fund_flow`、`btc_adoption` |
| `leverage_microstructure_analyst` | `derivatives_crowding`、`trade_structure_flow`、`options_volatility` |
| `onchain_market_structure_analyst` | `onchain_valuation`、`crypto_breadth`、`btc_total_state`、`kline_orderflow` |

每个 analyst input 必须包含 `pack_id / controller_run_id / p2_radar_run_id / p3_run_id / analyst_id / assigned_modules / global_context / evidence_items / analyst_history`。

每个 analyst output 必须包含 `analyst_id / vote / confidence / confidence_discount / time_horizon / key_claims / conflicting_evidence / missing_evidence / risk_flags / publish_constraints / history_delta`。

Schema 还必须为 `cross_exam_challenge`、`cross_exam_revision`、`judge_synthesis`、`adversarial_review` 和 `final_controller_json` 提供结构化定义。所有输出必须能被 JSON Schema 或 Pydantic model 校验，且所有 claim 必须引用当前 Evidence Pack 内的 `evidence_id`。

## 2026-05-21 执行结果

已完成 P4-C01 第一版 Schema 实现：

- 新增 `backend/src/onlybtc/p4/constants.py`
  - `ANALYST_MODULES`
  - `SIGNED_EVENT_METRICS`
- 新增 `backend/src/onlybtc/p4/schemas.py`
  - `AnalystInput`
  - `AnalystOutput`
  - `AgentEvidenceItem`
  - `AnalystHistory`
  - `CrossExamChallenge`
  - `CrossExamRevision`
  - `JudgeSynthesis`
  - `AdversarialReview`
  - `FinalControllerJson`
- `backend/src/onlybtc/p4/evidence_pack.py` 改为复用公共 constants，避免 P4-C06/P4-C16 后续重复维护分析师模块映射。
- 新增测试 `backend/tests/test_p4_schemas.py`，覆盖：
  - analyst input 的模块归属校验；
  - analyst input 禁止混入越权 Radar evidence；
  - key claim 必须引用 evidence ids；
  - cross-exam / judge / final controller JSON schema 可校验。

验证：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_schemas.py backend/tests/test_p4_evidence_pack.py backend/tests/test_p4_radar_coverage.py -q
.\.venv\Scripts\ruff.exe check backend/src/onlybtc/p4 backend/tests/test_p4_schemas.py backend/tests/test_p4_evidence_pack.py
```

结果：

- `6 passed`
- `ruff: All checks passed`
