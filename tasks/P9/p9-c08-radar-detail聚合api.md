# P9-C08 Radar Detail 聚合 API

## 状态

DONE

## 当前架构对齐（2026-05-22）

Radar Detail API 必须基于 P4.5 evidence pack 聚合单个 module，同时保留 P2 radar output 回链。

新增/调整 API：

- `GET /api/p45/radar-modules/latest`
- `GET /api/p45/radar-modules/{module_id}`

DTO 必须包含 module score/direction/strength/confidence/quality、support/pressure drivers、metric 列表、scored evidence 字段、source/freshness 字段、duplicate/horizon 权重字段、run lineage。

旧 `GET /api/radars/{module_id}` 可保留兼容，但 P5 主线使用 `/api/p45/radar-modules/{module_id}`。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

实现雷达详情页 API。

## API

- `GET /api/p45/radar-modules/latest`
- `GET /api/p45/radar-modules/{module_id}`

## SQLite 依赖

- radar_outputs
- feature_values
- module_json_outputs
- evidence_items
- source_health_events
- invalidation_conditions
- runs

## Vue3 对应任务

- P5-C17

## 验收标准

- [x] 返回模块信号、特征计算、证据、反证、上游来源和模块 JSON。
- [x] 返回 P2 radar output 回链。
- [x] 返回 scored evidence 的 source/freshness/duplicate/horizon 权重字段。
- [x] 返回 support/pressure/conflict drivers。
- [x] 数据质量折扣和 fallback/stale 计数在 summary/source_freshness 中明确。
- [x] `POST /api/radars/{module_id}/rerun` 不在 P5 主线使用，后续若需要单模块重跑应拆独立 Run Logs 操作卡。

## 执行记录（2026-06-23）

- `latest_radar_modules()` 增加：
  - `count`
  - `radar_modules` alias
- `radar_module_detail()` 增加：
  - `module_id`
  - `summary`
  - `support_drivers`
  - `pressure_drivers`
  - `conflict_drivers`
  - `source_freshness`
  - `weighting`
  - `p2_radar_output`
  - `runtime_module`
  - `module_json`
- 新增 helper：
  - `_p2_radar_output`
  - `_runtime_module_for`
  - `_radar_detail_summary`
  - `_radar_source_freshness`
  - `_radar_metric_weighting`
- 增强 focused test，锁定 Radar Detail 聚合字段与 P2 回链。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py::test_p45_evidence_and_module_filters_use_scored_payload backend\tests\test_p45_dashboard_api.py::test_p45_radar_module_detail_exposes_composite_semantics -q` -> 2 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\api\p45_dashboard.py backend\tests\test_p45_dashboard_api.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\tests\test_p45_dashboard_api.py --select I,F` -> passed。

## Notes

- 本卡只做 P4.5/P2/Radar Runtime 到 API DTO 聚合，不修改 radar scoring、module rerun、freshness 或 data quality 业务判断。
- `backend/src/onlybtc/api/p45_dashboard.py` 存在历史 E501 长行债务，本卡未做无关格式化。
