# P9-C02 Dashboard 与 BTC Overview 聚合 API

## 状态

DONE

## 当前架构对齐（2026-05-22）

本卡改为 P4.5 Dashboard / BTC Overview 聚合 API。旧 `/api/dashboard/current` 可保留兼容，但 P5 主线必须消费 P4.5 DTO。

新增/调整 API：

- `GET /api/p45/dashboard/latest`
- `GET /api/p45/overview/latest`

Dashboard DTO 必须聚合 run lineage、P4.5 `final_view/decision_card/aggregation_audit/horizon_views/contract_validation`、14 个 Radar module、Evidence count、DeepSeek LLM research、四分析师 LLM 状态、Data Quality warning。

Overview DTO 必须返回 `decision_card`、`why_not_strong`、`score_normalization`、support/pressure/dominant drivers、watch rules。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

实现 Dashboard 主拓扑和 BTC Overview 的聚合 API。

## API

- `GET /api/p45/dashboard/latest`
- `GET /api/p45/overview/latest`

## SQLite 依赖

- P4.5 final payload
- P4.5 evidence pack payload
- P4.5 radar module scores
- P3 algorithm alerts
- P4.5 LLM appendix payload
- P4.5 invalidation / confirmation rules
- P4.5 contract validation
- Legacy dashboard_snapshots / llm_debates / judge_syntheses 仅作兼容参考

## Vue3 对应任务

- P5-C01
- P5-C09

## 验收标准

- [x] Dashboard API 返回 BTC 中心状态、雷达节点、预警队列、多 LLM 摘要、数据质量。
- [x] Overview API 返回 Key Drivers、Conflicting Evidence、Confidence Explanation、Watch Next。
- [x] 所有核心返回对象带 run lineage 与可跳转 id。

## 执行记录（2026-06-23）

- 确认 `GET /api/p45/dashboard/latest` 已由 P4.5 final payload 聚合：
  - `run_lineage`
  - `final_view` / `decision_card`
  - `aggregation_audit`
  - `horizon_views`
  - `contract_validation`
  - radar modules / evidence count
  - LLM summary
  - data quality
  - audit reports
- 确认 `GET /api/p45/overview/latest` 已接入 P4.5 DTO。
- 为 Overview 增加顶层 contract aliases：
  - `why_not_strong`
  - `score_normalization`
  - `support_drivers`
  - `pressure_drivers`
  - `dominant_drivers`
  - `conflicting_evidence`
  - `confidence_explanation`
  - `watch_rules`
- 增强 `test_p45_dashboard_bundle_exposes_final_view_and_lineage`，锁定 Dashboard/Overview 聚合字段。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py::test_p45_dashboard_bundle_exposes_final_view_and_lineage backend\tests\test_p45_dashboard_api.py::test_p45_api_exposes_direct_trend_v22_contract -q` -> 2 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\api\p45_dashboard.py backend\tests\test_p45_dashboard_api.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\tests\test_p45_dashboard_api.py --select I,F` -> passed。

## Notes

- `backend/src/onlybtc/api/p45_dashboard.py` 存在历史 E501 长行债务，本卡未做无关格式化。
