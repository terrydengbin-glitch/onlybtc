# P5-C20 Vue3 API Client、状态管理与实时推送

## 状态

DONE

## 当前架构对齐（2026-05-22）

Vue API client 需要围绕 P9 聚合 DTO 建模，不直接读取 SQLite/HTML。

核心 client 方法：`getP45DashboardLatest()`、`getP45OverviewLatest()`、`getP45RadarModulesLatest()`、`getP45RadarModule(moduleId)`、`getP45Evidence(params)`、`getP45EvidenceItem(evidenceId)`、`getP45ArticlesLatest()`、`getP45AnalystsLatest()`、`getP45LlmLatest()`、`getP45InvalidationLatest()`、`getDataQualityLatest()`、`getSourceDetail(sourceId)`、`runP45FullWithLlm()`。

前端 store 的 canonical context 为 `final_run_id`，并派生 `collect_run_id / p2_radar_run_id / p3_run_id / pack_id`。

## Dashboard 实现对齐（2026-05-22）

P5 Dashboard 像素级还原阶段必须先使用统一 client/store，不允许组件内部散落 `fetch()`：

- Dashboard load：并发拉取 dashboard / overview / radar modules / alerts / invalidation / data quality / runs / audit reports。
- Route context：从 Dashboard 点击 Radar/Evidence/Article/Run Logs 时必须保留 `final_run_id` 与相关 filter。
- 历史模式：History Replay 页设置 `isHistorical=true` 后，实时推送不得覆盖当前 payload。
- 错误态：API 返回错误必须带 `endpoint`、`run_id`、`module_id` 或 `source_id` 可观测信息。
- Loading skeleton 必须按高保真布局占位，避免数据加载后布局跳动。

## 所属 Phase

P5 Dashboard 全量可视化

## 任务目标

建立 Vue3 前端 API client、页面状态管理、SSE/WebSocket 订阅和错误状态展示。

## UI 依据

- [ui方案-p5-dashboard.md](../../ui方案-p5-dashboard.md)

## FastAPI 依赖

- P9-C01 API DTO。
- P9-C10 SSE/WebSocket 实时推送。

## SQLite 依赖

- 通过 FastAPI API 间接依赖。

## 实施范围

- API client 封装。
- 页面 loading / error / stale / empty 状态。
- Realtime dashboard subscription。
- Run Once progress subscription。
- 历史模式禁止订阅实时覆盖。
- 统一保存 run context：`collect_run_id`、`p2_radar_run_id`、`p3_run_id`、`pack_id`、`article_run_id`、`final_run_id`、`llm_research_run_id`、`llm_analyst_run_id`。
- API 错误、fallback、runtime failure、stale、historical mode 都进入统一 UI state，不由页面各自猜测。
- 所有页面只消费 P9 聚合 API，不直接读取 SQLite。

## 验收标准

- 所有页面通过统一 client 请求。
- Dashboard 首屏无裸 `fetch()`，所有数据都通过 P5-C20 client/store。
- Dashboard 并发请求失败时，局部降级显示，不导致整页空白。
- API 错误能显示 source_id / module_id / run_id。
- 实时推送不会污染 History Replay。
- 同一用户路径中从 Dashboard 跳到 Evidence/Radar/LLM/Article 时 run context 不丢失。
