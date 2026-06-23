# P9-C09 History Replay 聚合 API 与历史模式

## 状态

DONE

## 当前架构对齐（2026-05-22）

History Replay 以 P4.5 `final_run_id` 为锚点，不以旧 snapshot_id 为主键。

新增/调整 API：

- `GET /api/p45/history`
- `GET /api/p45/history/{final_run_id}`

历史详情必须冻结并返回 final payload、evidence pack、deterministic analyst articles、LLM research、LLM analysts、P1/P2/P3/P4.5 run lineage、生成时间、contract status。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

实现历史回放 API，保证历史模式只读取 snapshot，不读取当前实时状态。

## API

- `GET /api/p45/history/{final_run_id}`
- `GET /api/p45/history`

## SQLite 依赖

- P4.5 historical final payload
- P4.5 historical evidence pack payload
- P4.5 historical LLM appendix payload
- replay_scores
- calibration_notes
- articles
- runs
- Legacy dashboard_snapshots / llm_debates 仅作兼容参考

## Vue3 对应任务

- P5-C18

## 验收标准

- [x] 历史状态不被当前数据覆盖。
- [x] 历史详情以 `final_run_id` 为锚点，返回 frozen payload。
- [x] 历史详情返回 final payload、evidence pack、deterministic analyst articles、LLM research、LLM analysts。
- [x] 历史详情返回 P1/P2/P3/P4.5 run lineage、生成时间、contract status。
- [x] 返回 replay scores 与 calibration notes；校准备注只读，不直接修改生产权重。
- [x] 提供 `GET /api/p45/history` 历史列表。

## 执行记录（2026-06-23）

- 新增 `GET /api/p45/history`。
- 新增 `history_list()`：
  - `items`
  - `count`
  - `history_mode`
  - `history_url`
- `history(final_run_id)` 增加：
  - `history_mode`
  - `created_at`
  - `contract_status`
  - `llm_research`
  - `llm_analysts`
  - `replay_scores`
  - `calibration_notes`
- `history_mode` 明确：
  - `anchor=final_run_id`
  - `read_only=true`
  - `historical_payload_frozen=true`
  - `uses_latest_runtime_state=false`

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py::test_p45_history_returns_frozen_final_payload backend\tests\test_p45_dashboard_api.py::test_p45_history_list_uses_final_run_id_anchor backend\tests\test_p45_dashboard_api.py::test_p45_history_replay_projects_btc_total_state_v2_from_sqlite -q` -> 3 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\api\p45_dashboard.py backend\src\onlybtc\api\app.py backend\tests\test_p45_dashboard_api.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\api\app.py backend\tests\test_p45_dashboard_api.py --select I,F` -> passed。

## Notes

- 本卡只读历史 payload / replay_scores / calibration_notes，不写校准备注，不修改生产权重。
- 旧 `snapshot_id` 不作为 P5 主线 replay anchor；主线锚点为 `final_run_id`。
