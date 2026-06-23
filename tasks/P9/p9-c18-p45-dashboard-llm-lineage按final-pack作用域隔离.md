# P9-C18 P45 Dashboard LLM lineage 按 final_run_id/pack_id 作用域隔离

## 状态

DONE

## Phase

P9 FastAPI 聚合 API 与运维质控

## 背景

LLM off 的 full chain 本轮只应产出 P1/P2/P3/P4.5 deterministic final，不应把历史 LLM research / analyst run id 挂到当前 Dashboard lineage 上。

当前发现 `/api/p45/dashboard/latest` 会读取最新 LLM payload，导致本轮 `final_run_id/pack_id` 没有 LLM 时，仍显示上一轮 LLM run id。

## 目标

- Dashboard / Overview / Articles / Runs 等 P45 聚合 API 的 LLM payload 必须按当前 `final_run_id` 和 `pack_id` 作用域读取。
- `llm_research_run_id` 只在 payload.final_run_id 等于当前 final_run_id 时出现。
- `llm_analyst_run_id` 只在 payload.pack_id 等于当前 pack_id 时出现。
- LLM off / fast deterministic 本轮不得展示旧 LLM run id。
- 不影响历史回放按指定 final_run_id/pack_id 读取。

## 实现范围

- `backend/src/onlybtc/api/p45_dashboard.py`
  - `latest_bundle()` 按最新 final 的 `final_run_id` 和 `pack_id` 读取 LLM payload。
  - `_bundle_for_scope()` 按传入 scope 读取 LLM payload。
  - 增加 scoped LLM 查询 helper。
- `backend/tests/test_p45_dashboard_api.py`
  - 增加 stale LLM lineage 隔离测试。

## DoD

- LLM off 本轮 Dashboard `run_lineage.llm_research_run_id` 为 null。
- LLM off 本轮 Dashboard `run_lineage.llm_analyst_run_id` 为 null。
- 如果同一 final_run_id/pack_id 存在 LLM payload，则能正常显示本轮 LLM run id。
- FastAPI 测试通过。

## 关联任务

P9-C17, P5-C38, P9-C16, P9-C15

## Execution Record

- `latest_bundle()` now resolves LLM research by the current `final_run_id`.
- `latest_bundle()` now resolves analyst LLM by the current `pack_id`.
- Scoped bundle loading uses the same final/pack LLM isolation.
- Legacy `skip_llm=true` jobs now report `execution_profile=fast_deterministic` in job status.
- Added tests for stale LLM lineage isolation and legacy skip-LLM profile derivation.

## Verification

- `.\.venv\Scripts\python.exe -m pytest backend/tests/test_p45_dashboard_api.py -q`
- Result: `10 passed`.
- `npm run build`
- Result: build passed.
