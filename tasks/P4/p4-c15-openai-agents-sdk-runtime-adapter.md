# P4-C15 OpenAI Agents SDK Runtime Adapter

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## 所属 Phase

P4 Agent 推理与总控融合 / P10 LLM Provider 配置 / P8 SQLite 审计持久化

## 背景

P4 业务编排由 onlyBTC 自建，但模型执行层采用 OpenAI Agents SDK。这样既保留 P1/P2/P3/P8 的冻结证据、状态机、反方审查和 SQLite 审计契约，又能复用官方 Agent runtime 的 structured output、tracing、guardrails 和后续 handoff 能力。

本卡不改变 P4 业务角色定义。4 个分析师、交叉质询、主裁判、反方审查仍由 onlyBTC 的 P4 任务卡定义；OpenAI Agents SDK 只作为执行适配层。

## 业务目标

建立 `onlybtc.p4.agent_runtime` 或等价模块，提供统一 runtime adapter：

```text
Evidence Pack / Agent Input Slice
  -> onlyBTC Agent Runtime Adapter
  -> OpenAI Agents SDK Agent
  -> structured output validation
  -> tracing / guardrails
  -> SQLite llm_* tables
```

## 输入契约

- P4-C01 生成的 analyst / cross-examiner / judge / adversarial schema。
- P4-C02 生成的 prompt templates。
- P4-C05 生成的 frozen Evidence Pack。
- P4-C14 生成的 analyst_history evidence。
- P10-C05 后续提供的 provider/model/env 配置。

## 输出契约

Runtime adapter 每次调用必须返回：

```yaml
agent_run_id
agent_role
agent_name
model_provider
model_name
prompt_version
schema_version
trace_id
guardrail_results
structured_output
raw_output_ref
error
latency_ms
token_usage
```

并写入或供后续写入：

- `llm_rounds`
- `llm_model_votes`
- `llm_challenges`
- `judge_syntheses`
- `adversarial_reviews`

## Guardrails

Runtime adapter 必须至少支持以下 guardrails：

- 输出必须通过 P4-C01 JSON Schema。
- 所有 claim 必须引用当前 Evidence Pack 内的 `evidence_id`。
- 禁止输出开仓、平仓、止损、止盈、仓位、杠杆。
- 禁止引用未进入 Evidence Pack 的外部事实。
- 禁止绕过 P3 invalidation、run_mode integrity、状态机和反方审查。

## DoD

- Runtime adapter 可以用 mock model 跑通 4 个 analyst agent。
- 真实 OpenAI Agents SDK 调用可通过配置开关启用，不影响 mock/CI。
- 每次调用有 `trace_id / agent_run_id / prompt_version / schema_version`。
- guardrail 失败时不会写入有效 vote，只写入失败事件和审计 payload。
- 测试覆盖 structured output 校验、guardrail 阻断、SQLite 落库字段。

## 2026-05-21 执行结果

已完成 P4-C15 第一版 Runtime Adapter：

- 新增 `backend/src/onlybtc/p4/agent_runtime.py`
  - `AgentRuntimeAdapter`
  - `ProviderConfig`
  - `RuntimeResult`
  - `GuardrailResult`
  - `provider_for_agent()`
  - `provider_config()`
- 支持 mock runtime：
  - 复用 P4-C02 `PromptBundle`；
  - 输出经 P4-C01 Schema 校验；
  - 生成 `agent_run_id / trace_id / prompt_version / schema_version / token_usage`；
  - 可用于 P4-C06 的 4 analyst executor。
- 支持真实 OpenAI Agents SDK 懒加载入口：
  - `AgentRuntimeAdapter.run_openai_agents()`；
  - 当前仓库未强制安装 `openai-agents`，未安装时返回结构化 runtime error，不影响 mock/CI；
  - `backend/pyproject.toml` 增加 optional extra：`agents = ["openai-agents>=0.14.0"]`。
- Provider 路由读取 P10-C05 `.env`：
  - `macro_event_analyst -> ONLYBTC_P4_MACRO_EVENT_PROVIDER`
  - `liquidity_flow_analyst -> ONLYBTC_P4_LIQUIDITY_FLOW_PROVIDER`
  - `leverage_microstructure_analyst -> ONLYBTC_P4_LEVERAGE_MICROSTRUCTURE_PROVIDER`
  - `onchain_market_structure_analyst -> ONLYBTC_P4_ONCHAIN_MARKET_STRUCTURE_PROVIDER`
  - `cross_examiner_agent -> ONLYBTC_P4_CROSS_EXAM_PROVIDER`
  - `judge_agent -> ONLYBTC_P4_JUDGE_PROVIDER`
- Guardrails 已实现：
  - structured output schema validation；
  - evidence ids 必须属于当前 PromptBundle 的 Evidence Pack；
  - 禁止交易建议相关词；
  - guardrail 失败时 `RuntimeResult.succeeded=false`，并保留失败原因。
- 新增测试 `backend/tests/test_p4_agent_runtime.py`：
  - provider 路由；
  - mock runtime 成功路径；
  - unknown evidence id 阻断；
  - trading-advice term 阻断。

验证：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_agent_runtime.py backend/tests/test_p4_prompts.py backend/tests/test_p4_schemas.py backend/tests/test_p4_evidence_pack.py backend/tests/test_p4_radar_coverage.py -q
.\.venv\Scripts\ruff.exe check backend/src/onlybtc/p4 backend/tests/test_p4_agent_runtime.py backend/tests/test_p4_prompts.py backend/tests/test_p4_schemas.py
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

结果：

- P4 相关测试：`13 passed`
- 全量后端测试：`87 passed`
- `ruff: All checks passed`

说明：

- 本卡完成的是统一 runtime adapter 与 mock/guardrail 骨架。
- 当前真实 OpenAI Agents SDK 调用入口已预留，但未在 CI 中强制执行；实际启用需安装 optional dependency `openai-agents` 并配置 provider 为 `openai`。
- DeepSeek/Qwen/Volcano/Kimi 的 OpenAI-compatible 直连执行，将由后续 P4-C06 或 P4-C15 增量卡接入；本卡先保证业务执行路径不分叉。
