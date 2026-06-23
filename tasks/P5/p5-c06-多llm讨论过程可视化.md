# P5-C06 P4.5 LLM 附录摘要可视化（Legacy Debate 已隔离）

## 状态

LEGACY

## 当前架构对齐（2026-05-22）

本卡改为 P4.5 LLM Research 与四分析师 LLM 附录可视化，不再展示旧 P4 多模型 Debate 作为主流程。

页面读取：`GET /api/p45/llm/latest`、`GET /api/p45/analysts/latest`。

必须展示：LLM Research Writer 的 provider/model/runtime_mode/status/latency/error；四分析师 LLM 的 analyst_id、覆盖 Radar modules、status、provider/model、latency_ms、metric_seen、evidence_ids_used_count；并明确 `llm_article_scope=internal_reference`、`participates_in_final_view=false`。

旧 P4 CrossExam/Judge/Adversarial Review 若展示，必须进入 legacy 折叠区，不影响 P4.5 `final_view`。

## Legacy 标记

旧任务语义“多 LLM 讨论过程可视化”已废弃为 Legacy。P5 主 Dashboard 不再展示旧 P4 Debate / CrossExam / Judge / Adversarial Review 作为主流程，不再从旧 `llm_debates` 推导系统结论。

本卡保留的原因是：Dashboard 仍需要一个 LLM 状态摘要区，但内容改为 P4.5 的 DeepSeek Research Writer 与四分析师 LLM 附录状态。

## 所属 Phase

P5

## 任务目标

在主 Dashboard 中可视化 P4.5 LLM 附录摘要：DeepSeek Research Writer、四分析师 LLM、provider/model/status/latency/error、evidence 覆盖数量和 `internal_reference` 标记。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)
- [P5 Dashboard UI 原型](../ui/p5-dashboard-ui-prototype.md)
- [P5 子页面 UI 原型](../ui/p5-subpages-ui-prototype.md)

## 实施范围

- 显示 4 个 P4.5 LLM Analyst 的角色、覆盖 Radar 模块、status、provider/model、latency_ms、metric_seen、evidence_ids_used_count。
- 显示 DeepSeek Research Writer 的 provider/model/runtime_mode/status/latency/error。
- 显示 `llm_runtime_mode`、`llm_article_scope=internal_reference`、`participates_in_final_view=false`。
- 旧 P4 CrossExam/Judge/Adversarial Review 只允许作为 `legacy_p4_reference` 折叠显示。
- 从主面板跳转到 P5-C11 P4.5 LLM 分析附录页。
- 遵守 evidence + data、历史窗口、数据质量、反证机制和预警边界。
- 不输出交易建议，不引入开仓、止损、仓位或杠杆逻辑。

## 输入

- `GET /api/p45/llm/latest`
- `GET /api/p45/analysts/latest`
- P4.5-C09/P4.5-C10/P4.5-C18/P4.5-C19 输出

## 输出

- Dashboard LLM 附录摘要组件。
- P4.5 LLM 状态卡。
- Legacy P4 Debate 折叠区入口，如实现。

## 验收标准

- 与《开发文档.md》的当前 P4.5 主线一致。
- 用户能看到 LLM 只是内部研究附录，不参与 P4.5 `final_view` 主裁判。
- LLM 失败、timeout 或 `completed_with_llm_errors` 必须可见，但 deterministic 主报告仍可用。
- 关键状态、错误和数据质量可观测。
- 不绕过 P4.5 final_view、反证/确认规则、预警等级或数据质量约束。

## 依赖任务

P4.5-C09、P4.5-C10、P4.5-C18、P4.5-C19、P5-C11、P9-C04、P5-C25

## 备注

页面展示结构化 LLM 附录摘要和证据覆盖，不展示不可审计的隐藏推理链。
