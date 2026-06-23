# P9-C55 / BTC TimeScale Direct Trend API Contract

## 状态
DONE

## Execution Record

### 2026-06-22 / Start

- 前置 P8-C39 已完成，v2.2 replay snapshot 已可按 `run_id/snapshot_id/asof_ts` 查询。
- 本卡目标：FastAPI 透传 v2.2 主 payload，同时给 dashboard/overview/history/runtime cockpit 提供一致的 direct trend summary 与 freshness/replay snapshot 字段。

### 2026-06-22 / Done

- `backend/src/onlybtc/api/p45_dashboard.py`：
  - `/api/p45/dashboard/latest`、`/api/p45/overview/latest`、`/api/p45/history/{run_id}` 透传 `btc_timescale_judge` 与 `btc_timescale_replay_snapshot`。
  - 新增 `direct_trend_api` contract，明确输出 `snapshot_id/asof_ts/runtime_fresh/source_fresh/fallback/freshness_summary`。
  - 4h / 1d horizon 明确区分 `direct_trend_direction_score`、`direct_trend_acceptance_score`、`direct_trend_trust_score`、`event_trust_cap`、`radar_context_bias`。
  - 投影层兼容 v2.2 明确字段与历史 `direction_score/acceptance_score/trust_score` 字段。
- `backend/src/onlybtc/api/radar_runtime.py`：
  - `/api/radar-runtime/cockpit/latest` 读取最新 replay snapshot，返回 `btc_timescale_judge`、`btc_timescale_replay_snapshot`、`direct_trend_api`。
- `backend/tests/test_p45_dashboard_api.py`：
  - 覆盖 dashboard / overview / history 的 v2.2 API contract。
  - 覆盖 runtime cockpit latest 的 v2.2 replay contract。

Verification:

```text
python -m pytest backend/tests/test_p45_dashboard_api.py -k "direct_trend_v22_contract or radar_runtime_cockpit_exposes_latest_direct_trend_replay"
2 passed

python -m pytest backend/tests/test_p45_dashboard_api.py backend/tests/test_btc_timescale_replay.py backend/tests/test_p45_timescale_judge.py
36 passed

python -m compileall backend/src/onlybtc/api/p45_dashboard.py backend/src/onlybtc/api/radar_runtime.py backend/tests/test_p45_dashboard_api.py
passed
```

Live sanity:

```text
dashboard_schema = p45.btc_timescale_judge.v2.2
overview_schema = p45.btc_timescale_judge.v2.2
cockpit_schema = p45.btc_timescale_judge.v2.2
snapshot_id = p3c62-state-20260622155135-9d8cba
cockpit_4h_score = 11.39
```

## 目标

FastAPI 透传 `btc_timescale_judge.v2.2`，让 dashboard、overview、history、runtime cockpit 都能读到同一份 4h / 1d direct trend judge。

## API 范围

```text
/api/p45/dashboard/latest
/api/p45/overview/latest
/api/p45/history/{run_id}
/api/radar-runtime/cockpit/latest
```

## 契约要求

API 必须明确区分：

```text
module_level_radar_score
direct_trend_direction_score
direct_trend_acceptance_score
direct_trend_trust_score
event_trust_cap
radar_context_bias
runtime_fresh
source_fresh
```

## DoD

1. API 返回 `btc_timescale_judge.schema_version = p45.btc_timescale_judge.v2.2`。
2. 返回 4h / 1d direct evidence、radar_context、trust cap、状态机结果。
3. 若 v2.2 缺失，保留 v2.1 / horizon_views fallback，并显式标记 `fallback_used=true`。
4. API 明确区分：
   - module-level radar score
   - direct trend evidence score
   - event trust cap
   - source freshness
5. dashboard/latest 和 history replay contract 测试通过。
6. 前端不得需要解析 HTML 审计文件才能展示 v2.2。

## API 连贯性字段

所有返回 v2.2 的 API 必须透传：

```text
snapshot_id
asof_ts
source_window
freshness_summary
fallback_used
fallback_reason
runtime_fresh
source_fresh
```

API 不允许把 stale payload 包装成成功 fresh 状态。若数据可用但 source stale，HTTP 仍可 200，但 payload 必须明确：

```json
{
  "source_fresh": false,
  "freshness_state": "stale|partial",
  "fallback_used": true
}
```
