# P9-C06 Data Quality 与 Source Detail 聚合 API

## 状态

DONE

## 当前架构对齐（2026-05-22）

Data Quality API 必须聚合 P1/P2/P3/P4.5 质量边界，而不是只读 source health。

新增/调整 API：

- `GET /api/data-quality/latest`
- `GET /api/sources/{source_id}`

Data Quality DTO 必须包含 P1 source health/source_runs/raw/fallback/rate limit、collection freshness 与 business recency、P2 historical_fallback/source_resolution/conflict_count、P3 run_mode_integrity/scored evidence missing field summary、P4.5 contract_validation、LLM provider/model/status/latency/error。

若 freshness 缺失仅来自 unavailable metric，应返回 warning，不作为 API error。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

实现数据质量总览和数据源详情 API。

## API

- `GET /api/data-quality/latest`
- `GET /api/sources/{source_id}`

## SQLite 依赖

- data_quality_snapshots
- source_health_events
- fallback_events
- rate_limit_events
- module_discounts
- sources
- source_runs
- raw_observations
- normalized_metrics

## Vue3 对应任务

- P5-C14
- P5-C16

## 验收标准

- [x] Data Quality API 返回 confidence cap、module discounts、fallback、rate limit。
- [x] Data Quality API 聚合 P1/P2/P3/P4.5/LLM 质量边界。
- [x] Source Detail API 返回 source profile、raw response、normalized data、fallback chain。
- [x] raw response 仅返回脱敏预览，不返回完整敏感 payload。
- [x] freshness 缺失或 unavailable metric 继续作为 warning / quality boundary，不作为 API error。

## 执行记录（2026-06-23）

- `latest_data_quality()` 增加：
  - `quality_boundary`
  - `fallback_events`
  - `rate_limit_events`
  - `module_discounts`
  - `data_quality_snapshot`
- `quality_boundary` 按层级暴露：
  - `p1` source health / fallback / rate limit
  - `p2` historical fallback / source resolution / conflict summary
  - `p3` run mode integrity / metric count audit
  - `p45` contract validation / HTML contract
  - `llm` provider/model/status summary
- `source_detail()` 增加：
  - `fallback_chain`
  - `rate_limit_events`
  - `module_discounts`
  - `raw_observations[].payload_redacted`
  - `raw_observations[].raw_payload` redacted preview
- 新增 focused test 验证 Data Quality 与 Source Detail P9-C06 契约。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py::test_data_quality_source_health_failed_count_filters_healthy_runs backend\tests\test_p45_dashboard_api.py::test_data_quality_and_source_detail_project_p9_c06_contract -q` -> 2 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\api\p45_dashboard.py backend\tests\test_p45_dashboard_api.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\tests\test_p45_dashboard_api.py --select I,F` -> passed。

## Notes

- 本卡只做质量边界与 source detail DTO 投影，不改变 freshness / fallback / rate limit 的业务判定。
- `backend/src/onlybtc/api/p45_dashboard.py` 存在历史 E501 长行债务，本卡未做无关格式化。
