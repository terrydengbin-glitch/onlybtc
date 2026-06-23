# P8-C39 / BTC TimeScale Direct Trend Judge SQLite Replay

## 状态
DONE

## Execution Record

### 2026-06-22 / Start

- 前置 P1-C75 / P2-C43 / P3-C62 / P4.5-C48 已完成。
- 本卡目标：冻结 `btc_timescale_judge.v2.2` 到 SQLite 独立 replay snapshot 表，支持按 `run_id/snapshot_id/asof_ts` 回放。
- 边界：history replay 必须读取持久化 payload，不使用最新 direct evidence/state 重算历史。

### 2026-06-22 / DONE

- 新增 SQLite 表：`timescale_judge_snapshots`。
- 最小字段已落地：`snapshot_id/run_id/asof_ts/schema_version/payload_json/source_window_json/freshness_summary_json/fallback_used/fallback_reason/created_at`。
- 索引已落地：`idx_timescale_snapshot_id`、`idx_timescale_asof_ts`、`idx_timescale_schema_version`。
- `snapshot_id` 允许重复索引，`run_id` 用于 final replay 身份，避免多个 final run 共享同一个 P3 state snapshot 时互相覆盖。
- 新增 `TimescaleJudgeReplayRepository` 与 `onlybtc.direct_trend.replay`：
  - `save_timescale_judge_snapshot(...)`
  - `replay_timescale_judge(run_id/snapshot_id/asof_ts/latest)`
  - `list_timescale_judge_replays(...)`
- `run_p45_final_writer` 现在会在生成 v2.2 后同步冻结 replay snapshot，并在 final payload 写入 `btc_timescale_replay_snapshot` 摘要。
- 新增 CLI：`btc-timescale-replay`，支持 `--run-id`、`--snapshot-id`、`--asof-ts`、`--limit`。
- live verification：
  - `p45final-p8-replay-verify-202606221610` 与 `p45final-p8-replay-verify-202606221611` 都可按 `run_id` 回放。
  - 两个 final run 共享 `snapshot_id=p3c62-state-20260622155135-9d8cba`，未发生 run 覆盖。
  - replay payload：`schema_version=p45.btc_timescale_judge.v2.2`，4h=`range_chop`，`direction_score=11.39`，`acceptance_score=0.0`，`trust_score=95.1`，`display_score=10.83`，`source_fresh=true`。
- Verification：
  - `python -m pytest backend/tests/test_btc_timescale_replay.py` => 4 passed
  - `python -m pytest backend/tests/test_btc_timescale_replay.py backend/tests/test_p45_timescale_judge.py` => 10 passed
  - `python -m pytest backend/tests/test_btc_direct_trend_evidence.py backend/tests/test_btc_direct_evidence_registry.py backend/tests/test_btc_direct_trend_state_machine.py backend/tests/test_btc_timescale_replay.py backend/tests/test_p45_timescale_judge.py` => 19 passed
  - `python -m compileall backend/src/onlybtc/db/schema.py backend/src/onlybtc/db/session.py backend/src/onlybtc/db/repositories.py backend/src/onlybtc/direct_trend backend/src/onlybtc/p45/final_writer.py backend/src/onlybtc/cli.py` => passed

## 目标

持久化 `btc_timescale_judge.v2.2`，支持历史回放 4h / 1d direct evidence、状态机、trust cap、radar context 和 source freshness。

## 要求

1. `final_payload.btc_timescale_judge` 保存 v2.2 全量 JSON。
2. runtime daemon snapshot 保存最新 direct trend judge 摘要。
3. 支持按 `run_id / snapshot_id / asof_ts` 查询。
4. history replay 必须复现当时的 4h / 1d 状态，不能用当前最新数据重算。
5. 保存 direct evidence 的 `source_lineage / freshness / stale_reason / normalizer_version`。
6. 保存 v2.1 baseline 和 v2.2 candidate，供 P7 A/B 审计。

## DoD

1. SQLite 中能查到 v2.2 payload。
2. 4h / 1d direct evidence 的 source lineage 可追踪。
3. replay API 返回当时的 `direction_score / acceptance_score / trust_score / display_score`。
4. replay 能区分 `runtime_fresh` 与 `source_fresh`。
5. P7 审计能验证同一 snapshot 中 DB/API/UI 一致。
6. 如果 source stale，SQLite payload 不能伪装为 fresh。

## SQLite 最小字段

持久化记录至少包含：

```text
snapshot_id
run_id
asof_ts
schema_version
payload_json
source_window_json
freshness_summary_json
fallback_used
fallback_reason
created_at
```

索引要求：

```text
idx_timescale_snapshot_id
idx_timescale_asof_ts
idx_timescale_schema_version
```
