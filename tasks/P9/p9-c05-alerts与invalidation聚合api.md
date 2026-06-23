# P9-C05 Alerts 与 Invalidation 聚合 API

## 状态

DONE

## 当前架构对齐（2026-05-22）

Alerts 仍来自 P3，Invalidation/Confirmation 来自 P4.5 final payload。

新增/调整 API：

- `GET /api/p3/alerts/latest`
- `GET /api/p3/events/latest`
- `GET /api/p45/invalidation/latest`

Invalidation DTO 必须包含 `invalidation_rules`、`confirmation_rules`、结构化 conditions、人类可读 expression、`action_if_triggered`、`applies_when`、`horizon`、关联 metric/evidence/module。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

实现预警页和反证页 API。

## API

- `GET /api/p3/alerts/latest`
- `GET /api/p3/events/latest`
- `GET /api/p45/invalidation/latest`

## SQLite 依赖

- algorithm_alerts
- alert_events
- invalidation_conditions
- invalidation_events
- evidence_items
- replay_scores
- audit_logs

## Vue3 对应任务

- P5-C12
- P5-C13

## 验收标准

- [x] Alerts API 返回支持证据、冲突证据、升级/降级条件。
- [x] Invalidation API 返回触发距离、阈值、当前值和动作。
- [x] Invalidation v2 Workbench 保持 P9-C38 透传兼容。
- [x] Legacy invalidation / confirmation rules 标准化为前端可消费字段。
- [x] 人工 silence / resolve 动作不在本卡实现；当前前端主线消费只需要 latest 聚合 API，动作审计留给后续权限/审计卡。

## 执行记录（2026-06-23）

- `latest_invalidation()` 对 legacy rules 增加标准化投影：
  - `rule_kind`
  - `conditions`
  - `expression`
  - `action_if_triggered`
  - `applies_when`
  - `horizon`
  - `module_id`
  - `metric_ids`
  - `evidence_ids`
  - `distance_to_trigger`
  - `threshold`
  - `current_value`
- `latest_alerts()` 增加 P4.5 context：
  - `supporting_evidence`
  - `conflicting_evidence`
  - `escalation_conditions`
  - `downgrade_conditions`
  - `invalidation_context`
- 新增 focused test 锁定 P9-C05 alerts/invalidation 聚合契约。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py::test_p45_alerts_and_invalidation_project_p9_c05_contract backend\tests\test_p45_invalidation_workbench.py::test_final_writer_persists_and_api_passthroughs_workbench -q` -> 2 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\api\p45_dashboard.py backend\tests\test_p45_dashboard_api.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\tests\test_p45_dashboard_api.py --select I,F` -> passed。

## Notes

- 本卡不重算 invalidation 业务判断，只做 P3/P4.5 payload 到 API DTO 的结构化投影。
- `POST /api/alerts/{alert_id}/silence` / `resolve` 涉及人工动作、权限和 audit_logs，留给后续 P9-C11 权限审计范围或独立操作卡。
