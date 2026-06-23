# P4-C06 4 分析师 Agent 独立分析执行器

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

本卡必须对齐 P4-C12。多 LLM 独立盲审必须读取 frozen Evidence Pack：

- 不允许模型直接查询数据库最新状态。
- 每个模型输出必须包含 vote、confidence、evidence_ids、uncertainty、missing_evidence。
- 模型输出必须通过 P4-C01 Schema 校验。
- 模型不能输出交易建议。
- 盲审结果写入 `llm_model_votes`，并保留 prompt/version metadata。

## 2026-05-21 Agent 化重构补充

本卡不再把 DeepSeek/Qwen/火山/Kimi 当成 4 个业务角色。P4-C06 的业务角色固定为 4 个 Analyst Agent：

- `macro_event_analyst`
- `liquidity_flow_analyst`
- `leverage_microstructure_analyst`
- `onchain_market_structure_analyst`

执行器职责：

```text
Evidence Pack
  -> analyst input slice
  -> prompt template
  -> runtime adapter
  -> structured analyst output
  -> schema validation
  -> llm_model_votes
```

每个 analyst 必须只读取自己负责的 evidence slice、必要 global constraints 和自己的 `analyst_history`，并输出 `vote / confidence / confidence_discount / evidence_ids / missing_evidence / risk_flags / history_delta`。

本卡优先支持 mock runtime，真实 OpenAI Agents SDK 调用由 P4-C15 接入。无论 runtime 是 mock 还是真实模型，输出都必须走同一 Schema 和落库路径。

## 2026-05-21 执行结果

已完成 P4-C06 第一版 4 分析师 Agent 独立分析执行器：

- 新增 `backend/src/onlybtc/p4/analyst_executor.py`
  - `run_analyst_agents()`
  - 从 frozen Evidence Pack 读取 `evidence_items`；
  - 按 `ANALYST_MODULES` 切出 4 份 `AnalystInput`；
  - 调用 P4-C02 `build_analyst_prompt()`；
  - 调用 P4-C15 `AgentRuntimeAdapter.run_mock()`；
  - Runtime 输出通过 P4-C01 `AnalystOutput` Schema 和 guardrails；
  - 写入 `llm_debates / llm_rounds / llm_model_votes`。
- 新增 CLI：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-run-analysts --pack-id <pack_id> --debate-id <debate_id> --runtime-mode mock
```

- 新增测试 `backend/tests/test_p4_analyst_executor.py`，验证：
  - 4 个 analyst input 都来自 Evidence Pack；
  - 每个 analyst 有独立 evidence slice；
  - mock runtime 成功；
  - 4 条 `llm_model_votes` 落库；
  - `llm_debates` 与 `llm_rounds` 落库。

真实库 mock run 验收：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-run-analysts `
  --pack-id p4-pack-20260521082743-2bf998 `
  --debate-id debate-202605210-p4c06-mock `
  --runtime-mode mock
```

结果：

- `status=completed`
- `pack_id=p4-pack-20260521082743-2bf998`
- `debate_id=debate-202605210-p4c06-mock`
- `run_id=p3-20260521072600-d38029`
- `analyst_count=4`
- `succeeded_count=4`
- `failed_count=0`
- `votes_written_count=4`
- analyst evidence slices：
  - `macro_event_analyst`: 48
  - `liquidity_flow_analyst`: 25
  - `leverage_microstructure_analyst`: 22
  - `onchain_market_structure_analyst`: 27
- provider routing：
  - `macro_event_analyst -> deepseek / deepseek-reasoner`
  - `liquidity_flow_analyst -> qwen / qwen3.6-max-preview`
  - `leverage_microstructure_analyst -> volcano / doubao-seed-2-0-pro-260215`
  - `onchain_market_structure_analyst -> kimi / kimi-k2.6`

验证：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_analyst_executor.py backend/tests/test_p4_agent_runtime.py backend/tests/test_p4_prompts.py backend/tests/test_p4_schemas.py backend/tests/test_p4_evidence_pack.py backend/tests/test_p4_radar_coverage.py -q
.\.venv\Scripts\ruff.exe check backend/src/onlybtc/p4 backend/src/onlybtc/cli.py backend/tests/test_p4_analyst_executor.py backend/tests/test_p4_agent_runtime.py
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

结果：

- P4 相关测试：`14 passed`
- 全量后端测试：`88 passed`
- `ruff: All checks passed`

说明：

- 本卡完成的是 mock runtime 下的统一执行与落库闭环。
- 真实 LLM 直连执行将在后续增量中接入，仍复用本卡的 input slice、prompt、runtime result、guardrail 和落库路径。
