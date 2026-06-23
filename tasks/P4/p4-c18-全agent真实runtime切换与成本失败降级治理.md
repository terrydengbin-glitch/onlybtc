# P4-C18 全 Agent 真实 Runtime 切换与成本失败降级治理

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## Execution Record

2026-05-21 completed.

- Added full P4 runtime mode support for `runtime_mode=mock|llm`.
- Added runtime governance config:
  - `ONLYBTC_P4_LLM_TIMEOUT_SECONDS`
  - `ONLYBTC_P4_LLM_MAX_RETRIES`
  - `ONLYBTC_P4_LLM_MAX_CALLS_PER_RUN`
  - `ONLYBTC_P4_LLM_MAX_ESTIMATED_TOKENS_PER_RUN`
  - `ONLYBTC_P4_LLM_FALLBACK_POLICY`
- Extended `RuntimeResult` with `fallback_used` and `fallback_reason`.
- Added budget checks, timeout configuration, retry loop, and `run_llm_or_mock()` fallback entrypoint.
- Connected `runtime_mode=llm` to:
  - 4 analyst agents
  - cross-exam agent
  - judge agent
  - adversarial review agent
  - article writer agent from P4-C17
- Final Controller now records:
  - `runtime_mode`
  - `llm_runtime_integrity`
  - `agent_runtime_failures`
  - `fallback_used`
  - `fallback_reasons`
  - `llm_budget_summary`
- P4 HTML now includes `id="all-agent-runtime-audit"` with runtime integrity and Agent Runtime Matrix.
- Added regression tests for runtime fallback and P4 HTML runtime audit.

Latest validation:

- Mock chain: `p4-full-audit --no-collect-live --run-mode live --runtime-mode mock --article-runtime-mode mock` completed.
- Real LLM chain: `p4-full-audit --no-collect-live --run-mode live --runtime-mode llm --article-runtime-mode llm` completed.
- Latest real LLM run ids:
  - `p2_radar_run_id=radar-20260521103359-757537`
  - `p3_run_id=p3-20260521103359-2cbc40`
  - `evidence_pack_id=p4-pack-20260521103401-711b43`
  - `debate_id=debate-d4dc22e7e5c1`
  - `judge_synthesis_id=judge-049cb4ca792c`
  - `adversarial_review_id=review-28458698861c`
  - `snapshot_id=snapshot-3ae5eb0bec31`
- Runtime result:
  - `runtime_mode=llm`
  - `article_runtime_mode=llm`
  - `article_status=completed`
  - `llm_runtime_integrity=fallback_used`
  - `fallback_used=true`
  - `agent_runtime_failures=[]`
- Observed fallback reasons were correctly captured in Final JSON / HTML:
  - `liquidity_flow_analyst`: provider read timeout
  - `onchain_market_structure_analyst`: Kimi HTTP 400
  - `cross_examiner_agent`: schema validation miss on one LLM challenge
- `p4-dod-check`: `status=passed`, `passed_count=12`, `failed_count=0`.
- Tests: 15 passed for P4 runtime/article/full-chain prompt/schema group.
- Ruff: passed.

## 所属 Phase

P4 Agent 推理与总控融合 / P4-C15 Runtime Adapter / P4-C16 全链条审计 / P4-C17 中文文章输出

## 背景

P4-C17 已经把 `article_writer_agent` 接入真实 LLM，并通过 `article_runtime_mode=llm` 完成中文文章生成验证。

但当前 P4 主决策链仍然默认使用 `runtime_mode=mock`：

- 4 个分析师 Agent 仍主要走 mock 输出；
- Cross-exam Agent 仍主要走 deterministic/mock；
- Judge Agent 仍主要走 deterministic/mock；
- Adversarial Review Agent 仍主要走 deterministic/mock；
- 真实 LLM 已验证可用，但还没有成为 P4 主推理链的受控运行模式。

下一阶段需要把 P4 从“文章层真实 LLM”推进到“全 Agent 主链可真实运行”，同时必须治理成本、超时、失败、结构化输出不合约、provider 异常、部分 Agent 降级等问题，避免真实 LLM 运行把 P1/P2/P3/P4 全链条稳定性拖垮。

## 目标

新增 P4 全 Agent runtime 治理能力：

- 支持 `runtime_mode=llm`，让 4 个分析师、交叉质询、主裁判、反方审查都能走真实 LLM。
- 保留 `runtime_mode=mock` 作为测试和回归基线。
- 支持 per-agent provider 配置：
  - `ONLYBTC_P4_MACRO_EVENT_PROVIDER`
  - `ONLYBTC_P4_LIQUIDITY_FLOW_PROVIDER`
  - `ONLYBTC_P4_LEVERAGE_MICROSTRUCTURE_PROVIDER`
  - `ONLYBTC_P4_ONCHAIN_MARKET_STRUCTURE_PROVIDER`
  - `ONLYBTC_P4_CROSS_EXAM_PROVIDER`
  - `ONLYBTC_P4_JUDGE_PROVIDER`
  - `ONLYBTC_P4_ARTICLE_PROVIDER`
- 为全 Agent 真实运行加入成本预算、超时、重试、失败降级和审计追踪。
- 真实 LLM 输出必须通过 schema、evidence、state constraint、no-trading-advice guardrail。
- P4 HTML 必须清楚展示每个 Agent 的 runtime mode、provider、model、latency、token estimate、error、fallback 状态。

## 输入

- P4 Evidence Pack
- AnalystInput slices
- Analyst history evidence
- P3 invalidation / event / anomaly / divergence evidence
- Rule baseline
- State machine constraints
- `.env` 中各 provider 的 API key / base_url / model 配置
- P4-C17 article runtime trace

## 输出

- `runtime_mode=llm` 的全 Agent 执行路径。
- 全 Agent Runtime Trace：
  - `agent_name`
  - `agent_role`
  - `runtime_mode`
  - `provider`
  - `model`
  - `latency_ms`
  - `token_usage`
  - `schema_version`
  - `guardrail_results`
  - `fallback_used`
  - `error`
- 成本与预算治理：
  - 每 run 最大 LLM 调用次数；
  - 每 agent 超时；
  - 每 agent 最大重试次数；
  - 估算 token 预算；
  - 超预算时的降级策略。
- 失败降级治理：
  - 单个分析师失败时，是否允许使用 mock fallback；
  - Cross-exam 失败时，是否允许跳过或降级；
  - Judge 失败时，是否必须阻断 final controller；
  - Adversarial Review 失败时，是否必须阻断 publish；
  - fallback 必须进入 final JSON 和 HTML。
- P4 HTML 新增全 Agent Runtime 审计区块。
- 测试覆盖 mock / llm-fail / fallback / budget-exceeded / schema-invalid 场景。

## 建议实现范围

### 1. Runtime Mode 契约

统一 P4 runtime mode：

- `mock`: 全部 Agent 使用 deterministic/mock。
- `llm`: 全部可真实运行的 Agent 使用 OpenAI-compatible Chat Completions 或 OpenAI Agents SDK。
- `hybrid`: 允许指定部分 Agent 使用真实 LLM，其他 Agent 使用 mock。

第一阶段至少实现：

- `mock`
- `llm`

`hybrid` 可以作为后续扩展，但配置字段需要预留。

### 2. AgentRuntimeAdapter 增强

在 `onlybtc.p4.agent_runtime` 中增加：

- per-agent timeout；
- per-agent retry；
- provider HTTP error 分类；
- structured JSON repair / normalization；
- schema validation failure trace；
- fallback decision reason；
- token usage estimate；
- optional real token usage capture。

所有 runtime result 必须写入可追踪结构，不能只在日志里出现。

### 3. Executor 改造

需要检查并改造：

- `analyst_executor`
- `cross_exam`
- `judge`
- `adversarial_review`
- `final_controller`
- `p4_full_chain`

要求：

- `runtime_mode=llm` 时真实调用 4 分析师 Agent。
- Cross-exam 使用真实 LLM 或受控 fallback。
- Judge 使用真实 LLM；如果失败，默认阻断 final controller publish。
- Adversarial Review 使用真实 LLM；如果失败，默认 `publish_allowed=false` 或加入 hard constraint。
- Final Controller 必须消费 runtime trace 和 fallback state。

### 4. 成本与失败降级配置

新增配置建议：

- `ONLYBTC_P4_LLM_TIMEOUT_SECONDS`
- `ONLYBTC_P4_LLM_MAX_RETRIES`
- `ONLYBTC_P4_LLM_MAX_CALLS_PER_RUN`
- `ONLYBTC_P4_LLM_MAX_ESTIMATED_TOKENS_PER_RUN`
- `ONLYBTC_P4_LLM_FALLBACK_POLICY`

`ONLYBTC_P4_LLM_FALLBACK_POLICY` 建议枚举：

- `strict`: 任一关键 Agent 失败即阻断 publish。
- `fallback`: 非关键 Agent 可 fallback，但必须降 confidence。
- `audit_only`: 允许生成 HTML，但 final controller 标记不可发布。

默认建议：

- 本地测试：`fallback`
- 生产真实运行：`strict`

### 5. HTML 与 JSON 审计

P4 HTML 必须新增：

- 全 Agent runtime matrix；
- provider / model / latency / error / fallback table；
- guardrail result table；
- budget summary；
- failure and fallback summary；
- final controller 中展示 `llm_runtime_integrity`。

Final Controller JSON 建议新增字段：

- `runtime_mode`
- `llm_runtime_integrity`
- `agent_runtime_failures`
- `fallback_used`
- `fallback_reasons`
- `llm_budget_summary`

## 验收标准

- `p4-full-audit --run-mode live --runtime-mode mock --article-runtime-mode mock` 继续通过。
- `p4-full-audit --run-mode live --runtime-mode llm --article-runtime-mode llm` 能完成一次真实全链条运行。
- P1/P2/P3/P4 四份 HTML 均刷新。
- P4 HTML 显示所有 Agent 的 runtime trace。
- 真实 LLM 跑通时：
  - 4 分析师真实输出；
  - Cross-exam 真实输出；
  - Judge 真实输出；
  - Adversarial Review 真实输出；
  - Article Writer 真实输出；
  - `p4-dod-check` passed。
- 任一 Agent 失败时：
  - 不允许静默吞错；
  - HTML 必须显示失败；
  - final controller 必须记录 fallback 或 block；
  - confidence 必须降级或 publish 必须阻断。
- 超预算时：
  - 停止继续真实 LLM 调用；
  - 使用配置的 fallback policy；
  - HTML 明确显示 budget exceeded。
- Ruff 通过。
- P4 相关测试通过。

## 不做

- 不改 P1/P2/P3 指标算法。
- 不改 P4 角色分工。
- 不接 P5 页面。
- 不把 LLM 输出作为无约束交易建议。
- 不允许真实 LLM 引入 Evidence Pack 之外的外部事实。

## 依赖任务

P4-C01, P4-C02, P4-C05, P4-C06, P4-C07, P4-C08, P4-C09, P4-C10, P4-C14, P4-C15, P4-C16, P4-C17

## 建议执行顺序

1. 梳理当前各 P4 executor 的 mock/llm 分支。
2. 增强 `AgentRuntimeAdapter` 的 timeout/retry/fallback/budget trace。
3. 先让 4 分析师支持 `runtime_mode=llm`。
4. 再接 Cross-exam / Judge / Adversarial Review。
5. Final Controller 消费 runtime trace 和 fallback state。
6. P4 HTML 增加全 Agent runtime 审计区块。
7. 增加失败注入测试。
8. 跑一次 mock 全链条，确认回归不坏。
9. 跑一次真实 llm 全链条，确认 P1/P2/P3/P4 HTML 全刷新。
