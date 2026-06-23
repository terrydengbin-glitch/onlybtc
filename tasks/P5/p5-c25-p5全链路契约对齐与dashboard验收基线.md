# P5-C25 P5 全链路契约对齐与 Dashboard 验收基线

## 状态

DONE

## 当前架构对齐（2026-05-22）

P5 当前以 P4.5 为主线，不再以旧 P4 Agent Debate 作为默认数据源。旧 P4 的 debate / judge / adversarial review 仅作为 legacy appendix 或历史兼容视图，不进入 Dashboard 主裁判链。

统一主链路：

```text
P1 live collect
-> P2 14 Radar modules
-> P3 scored_metric_evidence / alerts / event windows
-> P4.5 research_report.v2
-> P5 Dashboard / sub pages
-> P9 FastAPI aggregation API
```

P5 全局 run context 必须包含：`collect_run_id`、`p2_radar_run_id`、`p3_run_id`、`pack_id`、`article_run_id`、`final_run_id`、`llm_research_run_id`、`llm_analyst_run_id`、`run_mode`、`runtime_mode`、`llm_runtime_mode`。

P5 主结论唯一来源是 P4.5：`final_view`、`decision_card`、`aggregation_audit`、`horizon_views`、`invalidation_rules`、`confirmation_rules`、`contract_validation`。

P5 页面必须优先消费 P9 聚合 API，不允许前端直接拼 SQLite 表或直接解析散落的 HTML 文件。P9 API 可以从 `module_json_outputs.payload` 读取 P4.5 产物，但返回给前端的 DTO 必须稳定、可版本化、可测试。

P5 子页面对齐矩阵：

| 页面 | 主数据源 | FastAPI 聚合 API |
|---|---|---|
| Dashboard | P4.5 final + P45 pack + P2/P3 quality | `GET /api/p45/dashboard/latest` |
| BTC Overview | decision_card / horizon_views / aggregation_audit | `GET /api/p45/overview/latest` |
| Radar Nodes | P2 modules + P3 scored module + P45 module scores | `GET /api/p45/radar-modules/latest` |
| Radar Detail | 单 module metrics / scores / freshness / evidence | `GET /api/p45/radar-modules/{module_id}` |
| Evidence | P45 evidence pack 118 条 scored evidence | `GET /api/p45/evidence` / `GET /api/p45/evidence/{evidence_id}` |
| Article | research_article / publish_article / LLM research | `GET /api/p45/articles/latest` |
| Analyst / LLM | deterministic analysts + DeepSeek analyst articles | `GET /api/p45/analysts/latest` / `GET /api/p45/llm/latest` |
| Alerts | P3 alerts / event windows / watch rules | `GET /api/p3/alerts/latest` |
| Invalidation | P4.5 invalidation_rules + confirmation_rules | `GET /api/p45/invalidation/latest` |
| Data Quality | P1/P2/P3/P4.5 contract warnings and source health | `GET /api/data-quality/latest` |
| Source Detail | P1 source_runs/raw/metric/fallback/source health | `GET /api/sources/{source_id}` |
| Run Logs | P1/P2/P3/P4.5/LLM lineage and command status | `GET /api/runs/{run_id}` + `GET /api/p45/runs/latest` |
| Audit Reports | P1/P2/P3/P4.5 原始 HTML 审计报告索引 | `GET /api/p45/audit-reports/latest` / `GET /api/runs/{run_id}/audit-reports` |
| History Replay | historical final payload + pack payload by run | `GET /api/p45/history` / `GET /api/p45/history/{final_run_id}` |

P5 禁止把旧 P4 的 `llm_debates`、`judge_syntheses`、`adversarial_reviews` 作为主状态。若页面展示 legacy P4，必须标记为 `legacy_p4_reference`。

P5 必须提供审计报告入口：Dashboard / Run Logs 上可打开 P1/P2/P3/P4.5 HTML 报告。HTML 报告是人类审计产物，不是 Vue3 数据源；Vue3 数据仍然只消费 P9 聚合 API。

## Dashboard 页面级验收补充（2026-05-22）

P5-C25 作为 P5 总基线，必须纳入 P5-C26 的 Dashboard 像素级还原标准：

- Dashboard 第一张页面以 `ui-references/p5-dashboard-high-fidelity.html` 为高保真基准。
- 每张页面实现前必须确认：UI 原型、对应任务卡、FastAPI endpoint、run context、质量字段、截图验收路径。
- 页面验收必须包含：桌面 1440、桌面 1920、移动 390 三个截图。
- Vue3 只消费 P9 聚合 API；HTML 审计报告只作为外链审计产物。
- 左侧导航、顶部栏、拓扑画布、右侧摘要、周期卡、预警规则、Run Logs 入口必须能点击进入对应子页面或抽屉。
- P5-C21 最终 DoD 需要把 P5-C26 的截图和 API smoke test 纳入验收矩阵。

## 所属 Phase

P5 Dashboard 全量可视化

## 任务目标

在进入 P5 实现前，统一对齐 P1/P2/P3/P4/P8/P9 已完成或已变更的真实数据契约，形成 Dashboard、子页面、API client、mock fixture 与 DoD 的共同验收基线。

P5 不再按早期 PPT/UI 静态模式实现，而是直接消费当前全链路产物：

- P1：真实 live 采集、双时间戳、business recency、source health、fallback、主源/候选源/多源冲突。
- P2：14 个 Radar module、全量指标覆盖、同 run `collect_run_id`、historical fallback 显式化、Radar 质检结果。
- P3：异常、背离、反证、预警、事件窗口每日 watch、post-event 风险总结、P3 审计 HTML 字段。
- P4.5：deterministic research_report.v2、DeepSeek Research Writer、四分析师 LLM 附录、中文文章、LLM runtime 成本/失败/fallback 治理。
- P8：SQLite 持久化、P4.5 final payload、evidence pack、LLM appendix、article/run logs、run_mode 隔离。
- P9：页面聚合 API 与 SSE/WebSocket 契约，前端不得直接拼 SQLite 表。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [ui方案-p5-dashboard.md](../../ui方案-p5-dashboard.md)
- [task index.md](../../task%20index.md)
- P1-C22、P2-C19/P2-C21、P3-C11/P3-C14、P4-C16/P4-C18/P4-C19、P8-C16

## 实施范围

1. 为 P5 所有页面建立统一 run context：
   - `collect_run_id`
   - `p2_radar_run_id`
   - `p3_run_id`
   - `pack_id`
   - `article_run_id`
   - `final_run_id`
   - `llm_research_run_id`
   - `llm_analyst_run_id`
   - `run_mode`
   - `runtime_mode`
   - `article_runtime_mode`
2. 明确页面只读边界：
   - Dashboard 实时态读取最新 P4.5 dashboard DTO。
   - History Replay 只读指定 `final_run_id`，不被实时推送覆盖。
   - Evidence/Radar/LLM/Article 页面必须能回溯到同一 run。
   - Audit Reports 只打开 HTML 文件，不参与前端数据计算。
3. 明确质量与降级可视化：
   - `collection_freshness_status`
   - `business_recency_status`
   - `feature_run_scope`
   - `historical_fallback`
   - `source_resolution`
   - `fallback_used`
   - `fallback_reason`
   - `llm_runtime_integrity`
   - `agent_runtime_failures`
   - `confidence_cap`
4. 明确人类可读输出：
   - Dashboard 默认显示简洁结论。
   - Overview / Article / LLM Appendix 必须展示中文可读段落。
   - 每个结论必须可追溯 evidence + data + history，不展示不可审计隐藏推理链。
5. 补齐 mock fixture：
   - 正常 run。
   - 数据源 fallback run。
   - 多源冲突 run。
   - LLM runtime fallback run。
   - History Replay run。
   - run_mode mixed history 审计提示。

## 输入

- P1/P2/P3/P4 最新全链路输出 HTML 与 SQLite 记录。
- P9 页面聚合 API DTO。
- P8 seed database / mock API fixture。

## 输出

- P5 页面共用数据契约说明。
- P5 mock fixture 维度清单。
- P5 DoD 验收矩阵。
- P1/P2/P3/P4.5 审计报告索引契约。
- 需要同步到 P5-C01 至 P5-C24 的页面级约束。

## 验收标准

- P5 每个页面都能说明读取哪个聚合 API、哪个 run context、哪些质量字段。
- Dashboard 页面与高保真参考完成像素级对齐，并通过 P5-C26 截图验收。
- Dashboard 真实 FastAPI 数据链路打通，不依赖静态 HTML 样例或 mock 数据作为生产输入。
- Dashboard、Evidence、Radar Detail、LLM Appendix、Data Quality、History Replay 都能展示同 run 追溯链。
- Dashboard / Run Logs 能打开同 run 的 P1/P2/P3/P4.5 HTML 审计报告。
- 页面能明确区分真实数据、历史 fallback、模型 fallback、source warning、多源冲突。
- P5-C21 DoD 必须覆盖本卡列出的 6 类 mock fixture。
- 不出现交易建议、仓位、杠杆、止损或买卖按钮。

## 完成记录（2026-05-22）

- 已复验 P5 当前主链路：P1 live collect -> P2 Radar -> P3 scoring/events/alerts -> P4.5 report v2 -> P5 Dashboard -> P9 FastAPI。
- 已更新 Dashboard 验收矩阵，补充 `/reports/{report_html}` 只读报告入口，避免报告按钮回退到 SPA 首页。
- 已运行 FastAPI smoke：`/api/p45/dashboard/latest`、`/api/p45/overview/latest`、`/api/p45/radar-modules/latest`、`/api/p3/alerts/latest`、`/api/p45/invalidation/latest`、`/api/data-quality/latest`、`/api/p45/audit-reports/latest`、`/api/p45/runs/latest`、`/reports/p45-research-report.html` 均返回 200。
- 已调整 Dashboard 默认 Radar 点位和拓扑高度，降低 1440 基线截图节点重叠风险。
- 已验证：`npm run build`、`python scripts/validate_p5_dashboard_contract.py`、前端禁用交易执行词扫描通过。
- 已生成基线截图：
  - `screenshots/p5-dashboard-1440.png`
  - `screenshots/p5-dashboard-1920.png`
  - `screenshots/p5-dashboard-mobile.png`

## 依赖任务

P5-C01 至 P5-C26、P9-C01 至 P9-C14、P8-C16、P1-C22、P2-C21、P3-C14、P4-C18

## 备注

本卡是 P5 进入实现前的总对齐卡。后续 P5 任意页面实现、优化或新增，都必须先同步本卡、对应页面任务卡、`task index.md`，必要时同步 `开发文档.md` 与 UI 方案。
