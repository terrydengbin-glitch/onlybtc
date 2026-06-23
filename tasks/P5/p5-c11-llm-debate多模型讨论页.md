# P5-C11 P4.5 LLM 分析附录页（Legacy Debate 已隔离）

## 状态

LEGACY

## 当前架构对齐（2026-05-22）

本页更名语义为“P4.5 LLM 分析附录页”。旧 P4 Debate 多模型讨论不是当前 P5 主流程。

FastAPI 读取：`GET /api/p45/llm/latest`、`GET /api/p45/analysts/latest`。

必须展示：DeepSeek Research Writer 中文研报、四分析师 LLM 板块文章、provider/model/status/latency/error、覆盖 Radar modules、evidence_ids_used、`internal_reference`。

若保留旧 P4 Debate 页面入口，必须标记为 `legacy_p4_debate`，并默认折叠，不参与 P4.5 `final_view`。

## Legacy 标记

旧任务语义“LLM Debate 多模型讨论页”已废弃为 Legacy。P5 当前主流程不再使用旧 P4 Debate / CrossExam / Judge / Adversarial Review。

本卡的新职责是展示 P4.5 LLM 分析附录：DeepSeek Research Writer 中文研报、四分析师 LLM 板块文章、证据覆盖、运行状态和错误降级。

## 所属 Phase

P5 Dashboard 全量可视化

## 任务目标

实现 P4.5 LLM 分析附录页，展示 DeepSeek Research Writer、四分析师 LLM 文章、覆盖 Radar module、evidence 引用、provider/model/status/latency/error，并明确这些内容是 `internal_reference`。

## UI 依据

- [P5 子页面 UI 原型](../ui/p5-subpages-ui-prototype.md)
- `ui-references/p5-subpages-high-fidelity.html#llm`

## FastAPI 依赖

- P9-C04：`GET /api/p45/llm/latest`
- P9-C04：`GET /api/p45/analysts/latest`

## SQLite / Payload 依赖

- P4.5 `module_json_outputs.payload`
- P4.5 LLM research payload
- P4.5 analyst articles payload
- Legacy P4 `llm_debates` / `judge_syntheses` / `adversarial_reviews` 仅可作为折叠参考

## 实施范围

- LLM Runtime Summary。
- DeepSeek Research Writer 中文研报。
- 四分析师 LLM 板块文章。
- Evidence coverage 摘要。
- Provider/model/status/latency/error。
- evidence chip / invalidation chip 跳转。
- 展示 4 个 P4.5 Analyst 各自负责的 Radar 模块、prompt role、证据引用和中文分析段落。
- 展示 LLM timeout、schema repair、fallback、`completed_with_llm_errors` 的非阻断状态。
- 旧 P4 Debate 如展示，必须折叠在 `legacy_p4_debate` 区块。
- 不展示不可审计隐藏推理链，只展示 `reasoning_summary`、中文文章段落和 evidence citations。

## 验收标准

- 页面不是聊天气泡流。
- 必须展示证据引用、覆盖模块、provider/model/status/latency/error。
- 页面必须醒目标记 `internal_reference`、`participates_in_final_view=false`。
- 旧 P4 Debate 不得污染 P4.5 `final_view`。
- `completed_with_llm_errors` 时必须有醒目的非阻断提示。
