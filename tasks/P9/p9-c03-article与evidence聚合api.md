# P9-C03 Article 与 Evidence 聚合 API

## 状态

DONE

## 当前架构对齐（2026-05-22）

本卡改为 P4.5 Article / Evidence 聚合 API。旧 `articles` / `evidence_items` 表可以作为 legacy，但 P5 默认读取 P4.5 `module_json_outputs.payload`。

新增/调整 API：

- `GET /api/p45/articles/latest`
- `GET /api/p45/evidence`
- `GET /api/p45/evidence/{evidence_id}`

Article DTO 必须返回 `research_article`、`publish_article`、`decision_card`、`contract_validation`、LLM research metadata、deterministic analyst appendix metadata。

Evidence DTO 必须返回 P4.5 scored evidence 字段：`metric_score`、`metric_effective_score`、`freshness_weight`、`horizon_weight`、`duplicate_adjustment`、`horizon_tags`、`duplicate_group_id`、`source_ts`、`collected_at`、`freshness_minutes`、`is_stale`、`p45_metric_brief`、`score_reason`。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

实现文章页和证据页的聚合 API。

## API

- `GET /api/p45/articles/latest`
- `GET /api/p45/articles/history`
- `GET /api/p45/evidence`
- `GET /api/p45/evidence/{evidence_id}`

## SQLite 依赖

- articles
- article_versions
- article_evidence_links
- evidence_packs
- evidence_items
- evidence_metric_links
- metric_values
- source_health_events

## Vue3 对应任务

- P5-C08
- P5-C10

## 验收标准

- [x] Article API 返回文章、决策卡、合同校验、数据质量说明。
- [x] Article API 返回 LLM research metadata、deterministic analyst metadata、LLM analyst metadata。
- [x] Evidence list API 返回 P4.5 scored evidence 字段。
- [x] Evidence detail API 返回 Claim / Data / Interpretation。
- [x] 没有可用 P4.5 final payload 时返回 `missing` envelope，不输出伪造 claim。

## 执行记录（2026-06-23）

- `latest_articles()` 增加：
  - `decision_card`
  - `contract_validation`
  - `data_quality`
  - `llm_research_metadata`
  - `deterministic_analyst_metadata`
  - `llm_analyst_metadata`
- `latest_evidence()` 的 evidence item 投影补齐 P9-C03 字段：
  - `metric_score`
  - `metric_effective_score`
  - `freshness_weight`
  - `horizon_weight`
  - `duplicate_adjustment`
  - `horizon_tags`
  - `duplicate_group_id`
  - `source_ts`
  - `collected_at`
  - `freshness_minutes`
  - `is_stale`
  - `p45_metric_brief`
  - `score_reason`
- `evidence_detail()` 增加顶层：
  - `claim`
  - `data`
  - `interpretation`
- 保留 scoped exact 与 stale metric fallback resolution 契约。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py::test_p45_evidence_and_module_filters_use_scored_payload backend\tests\test_p45_dashboard_api.py::test_p45_articles_latest_exposes_article_and_appendix_metadata backend\tests\test_p45_dashboard_api.py::test_p45_evidence_detail_supports_scoped_and_stale_resolution -q` -> 3 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\api\p45_dashboard.py backend\tests\test_p45_dashboard_api.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\tests\test_p45_dashboard_api.py --select I,F` -> passed。

## Notes

- 本卡只做 P4.5 payload -> API DTO 投影，不修改评分、文章生成、证据生产或 stale fallback 策略。
