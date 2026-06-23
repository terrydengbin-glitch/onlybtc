# P7-C03 Prompt 版本管理

## 状态

DONE

## 所属 Phase

P7

## 任务目标

建立 Prompt 版本管理与审计登记层，覆盖当前 P4 legacy Agent prompt、P4 article writer prompt、P4.5 LLM Research Writer 与 P4.5 Analyst Writer prompt surface。产物必须可追踪 prompt_id、prompt_version、content_hash、输出 schema、guardrails 与生产适用范围。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 新增 prompt registry，集中描述 prompt surface、版本、hash、schema、guardrails 和 runtime scope。
- 对 P4 legacy 多 Agent prompt 做兼容登记，不继续扩展 legacy 生产主线。
- 对 P4.5 LLM Research Writer、P4.5 Analyst Writer 做当前主线登记。
- 输出 prompt version audit JSON/MD 报告，供 P7-C08 mock/DoD 引用。
- 本任务不直接改写 LLM 业务 prompt 内容，不改变模型调用、fallback、发布门控或状态机逻辑。
- 遵守 evidence + data、历史窗口、数据质量、反证机制和预警边界。
- 不输出交易建议，不引入开仓、止损、仓位或杠杆逻辑。

## 输入

- `onlybtc.p4.prompts.PROMPT_VERSION` 与 P4 prompt bundle builders。
- `onlybtc.p45.llm_research_writer` 的 system/user prompt surface。
- `onlybtc.p45.llm_analyst_writer` 的 system/user prompt surface。
- P7-C01/P7-C02 recommendation-only 治理边界。
- 《开发文档.md》中 LLM 不替代规则、prompt 变更可追踪和禁止交易建议约束。

## 输出

- Prompt registry：`backend/src/onlybtc/governance/prompt_registry.py`。
- 报告生成脚本：`scripts/generate_p7_c03_prompt_version_report.py`。
- 测试：`backend/tests/test_p7_prompt_registry.py`。
- 报告：`reports/p7-c03-prompt-version-management-report.json/md`。

## 验收标准

- [x] 每个 prompt entry 有稳定 `prompt_id`、`prompt_version`、`content_hash`、`surface`、`owner_phase`、`runtime_scope`。
- [x] 当前生产主线 P4.5 research/analyst prompt 被登记。
- [x] P4 legacy prompt 被标记为 `legacy_compat`，不误认为新生产主线。
- [x] 所有 prompt entry 均包含禁止交易建议、只用输入 evidence、输出 schema/JSON 约束等 guardrail 标记。
- [x] 报告明确 `applied_to_production=false`，只做治理登记。
- [x] 测试覆盖 hash 稳定性、必备 guardrails、P4.5 主线覆盖和报告生成。
- [x] 不绕过状态机、反方审查、预警等级或数据质量约束。

## 执行记录

- 新增 `backend/src/onlybtc/governance/__init__.py`。
- 新增 `backend/src/onlybtc/governance/prompt_registry.py`。
- 新增 `scripts/generate_p7_c03_prompt_version_report.py`。
- 新增 `backend/tests/test_p7_prompt_registry.py`。
- 生成 `reports/p7-c03-prompt-version-management-report.json`。
- 生成 `reports/p7-c03-prompt-version-management-report.md`。
- 当前 registry 共 8 个 prompt entry：2 个 `p45_mainline`，6 个 `legacy_compat`。
- P4.5 active surfaces：
  - `p45.llm_research_writer.article`
  - `p45.llm_analyst_writer.article`
- P4 legacy surfaces：
  - `p4.analyst_agent.independent_review`
  - `p4.cross_examiner.challenge`
  - `p4.judge.synthesis`
  - `p4.adversarial_reviewer.review`
  - `p4.article_writer.analyst_article`
  - `p4.article_writer.final_observation`

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p7_prompt_registry.py -q`：5 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c03_prompt_version_report.py`：通过，生成 JSON/MD 报告。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\governance scripts\generate_p7_c03_prompt_version_report.py`：通过。

## 依赖任务

- P7-C01
- P7-C02
- P7-C08

## 备注

- P7-C03 的 registry 可作为后续运行链路写入 `prompt_version` 和 `prompt_hash` 的来源。
- 本任务先做离线可审计 registry，不强制改造现有 LLM runtime payload。
- 本任务未修改现有 prompt 文本或 LLM runtime 调用逻辑。
