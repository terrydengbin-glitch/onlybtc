# P4-C02 4 分析师 Agent Prompt 与证据约束

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

本卡必须对齐 P4-C12。Prompt 模板必须绑定 frozen Evidence Pack：

- Prompt 必须显式列出 evidence ids，不允许模型使用未给出的外部证据。
- 必须要求模型解释 data quality、source conflict、business recency、run_mode integrity 对结论的影响。
- 必须禁止开仓、平仓、止损、止盈、仓位、杠杆等交易建议。
- 当 P3 alert / invalidation 未触发时，模型不得强行制造风险警报。
- 当 `publish_impact` 或 `critical_blocked_by` 存在时，模型必须保守表达并说明约束。

## 2026-05-21 Agent 化重构补充

Prompt 模板从“模块 LLM”升级为“4 个专业 Analyst Agent + 后续质询/裁判 Agent”。每个 prompt 必须包含：

- 当前角色的专业边界。
- 允许消费的 `assigned_modules` 和 `source_layer`。
- 当前 Evidence Pack 的 `pack_id / run_id`。
- 必须引用的 `evidence_id` 列表。
- 禁止事项：外部事实、交易建议、未给出数据、越权判断最终 BTC 状态。
- 历史记忆边界：`analyst_history` 只能用于观点连续性，不得覆盖本轮证据。

四个分析师 prompt 必须有不同关注重点：

- `macro_event_analyst`：宏观发布节奏、利率/信用/亚洲风险、P3 事件窗口、publish constraints。
- `liquidity_flow_analyst`：美元流动性、ETF/基金流、stablecoin 与采用率的持续性和背离。
- `leverage_microstructure_analyst`：funding、OI、basis、期权、清算、交易结构拥挤度。
- `onchain_market_structure_analyst`：链上估值、市场广度、BTC 总状态、K 线和价格结构。

Prompt 必须要求输出方向判断、置信度、支撑证据、反证证据、数据质量折扣、缺失证据、历史观点变化，以及对其他分析师可能提出的质询点。

Prompt 不负责模型供应商选择。DeepSeek/Qwen/Kimi/OpenAI 等供应商只属于 P4-C15 runtime adapter 配置，不再等同于业务角色。

## 2026-05-21 执行结果

已完成 P4-C02 第一版 Prompt 模板实现：

- 新增 `backend/src/onlybtc/p4/prompts.py`
  - `build_analyst_prompt()`
  - `build_cross_examiner_system_prompt()`
  - `build_judge_system_prompt()`
  - `build_adversarial_reviewer_system_prompt()`
  - `PromptBundle`
- 4 个分析师 prompt 已按角色区分：
  - `macro_event_analyst`
  - `liquidity_flow_analyst`
  - `leverage_microstructure_analyst`
  - `onchain_market_structure_analyst`
- Prompt 明确绑定：
  - `pack_id / controller_run_id / p2_radar_run_id / p3_run_id`
  - `assigned_modules`
  - `allowed_source_layers`
  - 当前 Evidence Pack 内的 `evidence_ids`
  - `AnalystOutput` JSON Schema
- Prompt guardrails 已覆盖：
  - 禁止外部事实；
  - 禁止交易建议；
  - 禁止越权判断最终 BTC 总控状态；
  - 每个 claim 必须引用 evidence ids；
  - `analyst_history` 只能作为连续性上下文，不能覆盖本轮 P2/P3 evidence；
  - 数据质量、source conflict、business recency、fallback、run_mode integrity、P3 alert/event/invalidation 必须作为 confidence/publish 约束。
- 新增测试 `backend/tests/test_p4_prompts.py`，验证 prompt 与 Evidence Pack、Schema、guardrails、历史边界、质询/裁判/反方审查 prompt bundle 的契约。

验证：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_prompts.py backend/tests/test_p4_schemas.py backend/tests/test_p4_evidence_pack.py backend/tests/test_p4_radar_coverage.py -q
.\.venv\Scripts\ruff.exe check backend/src/onlybtc/p4 backend/tests/test_p4_prompts.py backend/tests/test_p4_schemas.py
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

结果：

- P4 相关测试：`9 passed`
- 全量后端测试：`83 passed`
- `ruff: All checks passed`
