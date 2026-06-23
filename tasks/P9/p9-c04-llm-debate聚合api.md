# P9-C04 P4.5 LLM 分析附录聚合 API（Legacy Debate 已隔离）

## 状态

LEGACY

## 当前架构对齐（2026-05-22）

本卡改为 P4.5 LLM 分析附录 API。旧 P4 `llm_debates` / `llm_rounds` / `judge_syntheses` 仅作为 legacy P4 reference，不是 P5 默认数据源。

新增/调整 API：

- `GET /api/p45/llm/latest`
- `GET /api/p45/analysts/latest`
- 可选兼容：`GET /api/legacy/p4/debates/{debate_id}`

P4.5 LLM DTO 必须返回 LLM Research Writer 和四分析师 LLM 的 provider/model/runtime_mode/status/latency_ms/error/article/evidence/radar_modules，并明确 `llm_article_scope=internal_reference`、`participates_in_final_view=false`。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

实现 P4.5 LLM 分析附录页 API。旧 P4 Debate API 只作为 legacy 兼容入口，不作为 P5 默认数据源。

## API

- `GET /api/p45/llm/latest`
- `GET /api/p45/analysts/latest`
- 可选 legacy：`GET /api/legacy/p4/debates/{debate_id}`

## SQLite 依赖

- P4.5 `module_json_outputs.payload`
- P4.5 LLM research payload
- P4.5 analyst articles payload
- Legacy P4 `llm_debates` / `llm_rounds` / `judge_syntheses` / `adversarial_reviews` 仅作兼容参考

## Vue3 对应任务

- P5-C11

## 验收标准

- 返回 DeepSeek Research Writer、四分析师 LLM 文章、provider/model/runtime_mode/status/latency_ms/error、evidence/radar_modules 覆盖。
- 返回 `llm_article_scope=internal_reference`、`participates_in_final_view=false`。
- 不返回无 evidence_id 的关键结论作为正文结论；无数据内容只能作为 data boundary。
- 支持按 analyst_id / radar_module / evidence_id 过滤。
- 旧 Debate 字段若返回，必须在 `legacy_p4_reference` 下折叠。
