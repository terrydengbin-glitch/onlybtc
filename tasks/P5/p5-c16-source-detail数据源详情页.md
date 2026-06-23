# P5-C16 Source Detail 数据源详情页

## 状态

DONE

## 当前架构对齐（2026-05-22）

Source Detail 页以 P1/P8 持久化数据为主，必须能解释该 source 如何影响 P2/P3/P4.5。

FastAPI 读取：`GET /api/sources/{source_id}`。

展示字段：source profile、priority、fallback_source_id、latest source_run status/latency/error、raw observation 摘要、normalized metric values、collection_freshness_status、business_recency_status、stale_after_minutes、downstream radar modules、downstream evidence ids。

## 所属 Phase

P5 Dashboard 全量可视化

## 任务目标

实现单个数据源排障与验证页，展示 source profile、raw response、normalized data、fallback、错误和影响模块。

## UI 依据

- [ui方案-p5-dashboard.md](../../ui方案-p5-dashboard.md)
- `ui-references/p5-source-detail-page-*.png`

## FastAPI 依赖

- P9-C06：`GET /api/sources/{source_id}`

## SQLite 依赖

- sources
- source_runs
- raw_observations
- normalized_metrics
- source_health_events
- fallback_events

## 实施范围

- Source Header、Source Profile、Data Preview、Validation、Fallback Chain、Recent Errors、Affected Modules、Historical Quality。
- raw response 必须脱敏。
- 展示 `collection_freshness_status`、`business_recency_status`、freshness policy、last_collected_at、observed_at。
- 展示主源/候选源/fallback 源关系，以及影响到哪些 Radar feature 与 Evidence item。
- 对 BLS 403、FXStreet 无 actual、semi-automated human challenge 等状态给出业务语义解释。

## 验收标准

- fallback active source 必须明确。
- raw response 不暴露 API key / cookie / token。
- 能跳转 Data Quality、Run Logs、Evidence。
- Source Detail 必须区分采集失败、业务未发布、人工验证需要、历史 fallback。

## 完成记录

- `frontend/src/App.vue`：Source Detail 页面接入 `GET /api/sources/{source_id}` 的 `source/runs/raw_observations/metrics`。
- `frontend/src/App.vue`：新增 Source Header、Source Profile、fallback source、latest source run、freshness policy、raw observation preview、normalized metrics、downstream evidence 和 validation actions。
- `frontend/src/App.vue`：补充 BLS 403、无 actual、human challenge、timeout、fallback 等状态的业务语义解释。
- `frontend/src/App.vue`：Source Detail 可跳转 Data Quality、Run Logs、Evidence，并从 Evidence / Radar Detail / Data Quality 进入。
- `frontend/src/styles.css`：补齐 Source Detail 页面、source picker、source hero、source detail grid 的响应式样式。
- 验证通过：
  - `npm run build`
  - `python scripts/validate_p5_dashboard_contract.py`
  - `python scripts/validate_p5_page_dod.py`
