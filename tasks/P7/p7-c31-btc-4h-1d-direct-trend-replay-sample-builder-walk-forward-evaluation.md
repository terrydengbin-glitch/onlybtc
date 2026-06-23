# P7-C31 / BTC 4H-1D Direct Trend Replay Sample Builder & Walk-forward Evaluation

## 状态
DONE

## Execution Record

### 2026-06-23 / Done

- 新增评估 runner：`scripts/generate_btc_4h_1d_direct_trend_evaluation.py`。
- 批量生成并落库 `70` 条历史 replay samples，目标 schema 为 `p45.btc_timescale_judge.v2.2`。
- sample builder 使用当前生产 latest asof 前 24h 作为 `max_sample_asof`，避免评估样本覆盖生产 latest replay。
- 固化评估 split：
  - method = `walk_forward_with_purged_embargo`
  - random_k_fold = `forbidden`
  - embargo_hours = `24`
  - fold_count = `4`
- 输出评估报告：
  - `reports/btc-4h-1d-direct-trend-evaluation-report.html`
  - `reports/btc-4h-1d-direct-trend-evaluation-report.md`
  - `reports/btc-4h-1d-direct-trend-evaluation-report.json`
- 评估结果：
  - overall_status = `PASS`
  - valid_sample_count = `70`
  - Rank IC / AUC / F1 / Precision@TopDecile / Whipsaw / False Breakout / Confidence Calibration 均输出有效样本指标。
  - Lead Time 与 Event Window Robustness 在当前历史窗口没有对应标签样本，报告中以 `coverage_status=not_applicable` 和明确 reason 标注，未静默混入 fresh metrics。
- 回填 P7-C30 并重跑 full-chain audit：overall_status = `PASS`，P7-C30 已升为 `DONE`。

### 2026-06-23 / Start

- 用户明确开始 P7-C31。
- 本卡承接 P7-C30 evaluation `PARTIAL` 缺口：本地 v2.2 replay snapshots 仅 2 个，无法计算 walk-forward 指标。
- 实施原则：优先复用 P8 replay repository 与 P7-C30 audit runner；评估 runner 禁止随机 K-fold，样本不足时必须输出显式 `not_enough_valid_samples`。

## 前置

- P1-C75 / BTC 4H/1D Direct Evidence Features
- P2-C43 / BTC 4H/1D Direct Evidence Registry
- P3-C62 / BTC 4H/1D Direct Trend State Machine
- P4.5-C48 / BTC 4H/1D Direct Trend Judge v2.2
- P8-C39 / BTC TimeScale Direct Trend Judge SQLite Replay
- P9-C55 / BTC TimeScale Direct Trend API Contract
- P5-C87 / BTC TimeScale Direct Trend UI Vue3
- P7-C30 / BTC 4H/1D Direct Trend Full Chain Audit = PARTIAL PASS

## Summary

P7-C30 已确认 4h / 1d direct trend 主链路完整，SQLite / FastAPI / runtime cockpit / Vue3 使用同一 `snapshot_id`，lineage matrix 27/27 pass。

当前唯一缺口是 evaluation：本地只有 2 个 `btc_timescale_judge.v2.2` replay snapshots，不足以做 walk-forward / purged split，也不能安全计算 Rank IC、AUC/F1、Precision@TopDecile、Whipsaw Rate、False Breakout Reduction、Lead Time、Confidence Calibration、Event Window Robustness。

本卡负责批量生成/回放足够多的 v2.2 snapshots，固化泄漏安全的评估 runner，并回填 P7-C30，使其从 `PARTIAL PASS` 升级为 `DONE`。

## Scope

### In Scope

- 批量生成或重放 `btc_timescale_judge.v2.2` snapshots。
- 建立 sample builder，确保每条样本有稳定的：
  - `run_id`
  - `snapshot_id`
  - `asof_ts`
  - `schema_version`
  - `source_window`
  - `freshness_summary`
  - `fallback_used`
  - 4h / 1d horizon scores
- 建立 walk-forward / purged / embargoed evaluation runner。
- 输出评估报告：

```text
reports/btc-4h-1d-direct-trend-evaluation-report.html
reports/btc-4h-1d-direct-trend-evaluation-report.md
reports/btc-4h-1d-direct-trend-evaluation-report.json
```

- 回填并重跑：

```text
reports/btc-4h-1d-direct-trend-audit-report.html
reports/btc-4h-1d-direct-trend-audit-report.md
reports/btc-4h-1d-direct-trend-audit-report.json
```

- 将 P7-C30 状态从 `PARTIAL PASS` 升为 `DONE`，前提是 evaluation DoD 满足。

### Out of Scope

- 不改 4h / 1d direct trend 交易语义阈值，除非评估报告明确创建后续校准任务卡。
- 不用随机 K-fold。
- 不用未来收益或未来事件信息参与当前时点特征构造。
- 不把 stale / fallback snapshot 静默当作 fresh 样本。

## Business Chain / Contract

```text
P1 direct evidence features
-> P2 direct evidence registry
-> P3 direct trend state machine
-> P4.5 btc_timescale_judge.v2.2
-> P8 timescale_judge_snapshots
-> P7 sample builder
-> P7 walk-forward evaluation
-> P7-C30 full chain audit backfill
```

核心 contract 字段：

```text
run_id
snapshot_id
asof_ts
schema_version = p45.btc_timescale_judge.v2.2
horizons.4h.direction_score
horizons.4h.acceptance_score
horizons.4h.trust_score
horizons.4h.display_score
horizons.1d.direction_score
horizons.1d.acceptance_score
horizons.1d.trust_score
horizons.1d.display_score
source_fresh
runtime_fresh
fallback_used
fallback_reason
source_window
freshness_summary
```

Evaluation target fields must be generated strictly after `asof_ts`, for example:

```text
future_return_4h
future_return_24h
trend_accepted_label
false_breakout_label
whipsaw_label
event_window_label
```

## Implementation Plan

1. Add a replay sample builder script or module.
   - Read historical source / metric windows from SQLite.
   - Generate deterministic v2.2 judge snapshots at eligible `asof_ts`.
   - Persist snapshots through the same P8 replay repository path.
   - Mark stale / fallback samples explicitly.

2. Add an evaluation runner.
   - Use walk-forward or purged / embargoed split.
   - Reject random K-fold.
   - Exclude samples with missing target windows from metric calculation.
   - Report skipped sample counts and reasons.

3. Compute required metrics.
   - Rank IC
   - AUC / F1 for `trend_accepted`
   - Precision@TopDecile
   - Whipsaw Rate
   - False Breakout Reduction
   - Lead Time
   - Confidence Calibration
   - Event Window Robustness

4. Generate reports.
   - HTML for human audit.
   - MD for task review.
   - JSON for machine-readable regression.

5. Re-run P7-C30 audit and update P7-C30.

## DoD

1. Sample builder can generate/replay enough v2.2 snapshots for evaluation, with a visible sample count threshold.
2. Every sample has `run_id/snapshot_id/asof_ts/schema_version` and freshness/fallback metadata.
3. Evaluation runner uses walk-forward or purged / embargoed split only.
4. Random K-fold is explicitly blocked or absent from code.
5. Evaluation report exists in HTML / MD / JSON.
6. Report includes all required metrics or explicit `not_enough_valid_samples` reason per metric.
7. `source_fresh=false` and `fallback_used=true` samples are either excluded or separately bucketed, never silently merged into fresh production metrics.
8. P7-C30 full-chain audit is regenerated and no longer reports evaluation `PARTIAL`.
9. P7-C30 task card and `task index.md` are updated from `PARTIAL PASS` to `DONE`.
10. Focused tests and compile checks pass.

## Test Plan

```text
python scripts/generate_btc_4h_1d_direct_trend_evaluation.py --help
python scripts/generate_btc_4h_1d_direct_trend_evaluation.py
python scripts/generate_btc_4h_1d_direct_trend_audit.py
python -m pytest backend/tests/test_btc_direct_trend_evidence.py backend/tests/test_btc_direct_evidence_registry.py backend/tests/test_btc_direct_trend_state_machine.py backend/tests/test_btc_timescale_replay.py backend/tests/test_p45_timescale_judge.py backend/tests/test_p45_dashboard_api.py -q
python -m compileall scripts backend/src/onlybtc/direct_trend backend/src/onlybtc/p45 backend/src/onlybtc/api
npm run build
```

## Risks / Notes

- 如果 SQLite 历史窗口不足，评估报告必须保留 `PARTIAL`，并输出最小缺口：缺多少 snapshots、缺哪些 target windows、哪些 source 不足。
- 不能用未来数据构造当前 snapshot。
- 不能为了让 P7-C30 DONE 而伪造指标。
- 评估结果如显示阈值或状态机问题，应新建独立校准任务，不在本卡静默改策略语义。
