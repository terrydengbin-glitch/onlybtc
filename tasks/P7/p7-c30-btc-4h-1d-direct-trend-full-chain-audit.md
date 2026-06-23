# P7-C30 / BTC 4H/1D Direct Trend Full Chain Audit

## 状态
DONE

## Execution Record

### 2026-06-23 / Evaluation Backfill Done

- P7-C31 已批量生成并落库 `btc_timescale_judge.v2.2` replay snapshots。
- 重新生成评估报告：
  - `reports/btc-4h-1d-direct-trend-evaluation-report.html`
  - `reports/btc-4h-1d-direct-trend-evaluation-report.md`
  - `reports/btc-4h-1d-direct-trend-evaluation-report.json`
- 评估结果：
  - overall_status = `PASS`
  - sample_count = `70`
  - valid_sample_count = `70`
  - split_policy = `walk_forward_with_purged_embargo`
  - random_k_fold = `forbidden`
  - fold_count = `4`
- 重新生成 P7-C30 full-chain audit 报告：
  - `reports/btc-4h-1d-direct-trend-audit-report.html`
  - `reports/btc-4h-1d-direct-trend-audit-report.md`
  - `reports/btc-4h-1d-direct-trend-audit-report.json`
- 审计结果：
  - overall_status = `PASS`
  - evaluation sample_count = `72`
  - lineage matrix = 27/27 `pass`
  - SQLite / FastAPI / runtime cockpit snapshot 仍一致：`p3c62-state-20260622155135-9d8cba`

### 2026-06-22 / Partial Pass

- 新增审计 runner：`scripts/generate_btc_4h_1d_direct_trend_audit.py`。
- 输出：
  - `reports/btc-4h-1d-direct-trend-audit-report.html`
  - `reports/btc-4h-1d-direct-trend-audit-report.md`
  - `reports/btc-4h-1d-direct-trend-audit-report.json`
- 审计结果：
  - overall_status = `PARTIAL`
  - core chain checks = 10/10 `PASS`
  - lineage matrix = 27/27 `pass`
  - SQLite / FastAPI / runtime cockpit snapshot 一致：`p3c62-state-20260622155135-9d8cba`
  - P4.5 schema = `p45.btc_timescale_judge.v2.2`
  - Event overlay 校验通过：只影响 trust / quality gate，不进入 direction trigger。
  - Radar module contribution 校验通过：只作为 `radar_context`，不替代 direct evidence。
  - Vue3 静态契约校验通过：UI 读取 v2.2、展示 direct evidence / radar context / BTC acceptance / event trust cap / freshness。
- 未完成项：
  - walk-forward / purged split 回测指标为 `PARTIAL`。
  - 本地仅有 2 个 v2.2 replay snapshots，不足以计算 Rank IC、AUC/F1、Precision@TopDecile、Whipsaw Rate、False Breakout Reduction、Lead Time、Confidence Calibration、Event Window Robustness。

Verification:

```text
python scripts/generate_btc_4h_1d_direct_trend_audit.py
overall_status = PARTIAL

python -m pytest backend/tests/test_btc_direct_trend_evidence.py backend/tests/test_btc_direct_evidence_registry.py backend/tests/test_btc_direct_trend_state_machine.py backend/tests/test_btc_timescale_replay.py backend/tests/test_p45_timescale_judge.py backend/tests/test_p45_dashboard_api.py -q
45 passed

python -m compileall scripts/generate_btc_4h_1d_direct_trend_audit.py backend/src/onlybtc/api/p45_dashboard.py backend/src/onlybtc/api/radar_runtime.py
passed

npm run build
passed
```

## 目标

对 `btc_timescale_judge.v2.2` 做全链路审计，确认 4h / 1d 不再是 radar module 综合分二次平均，而是真正消费 direct evidence。

## 审计链条

```text
P1 direct evidence metric_values
-> P2 direct_evidence registry
-> P3 4h/1d state machine
-> P4.5 btc_timescale_judge.v2.2
-> P8 SQLite snapshot/replay
-> P9 FastAPI
-> P5 Vue3 cards
-> P7 HTML audit
```

## HTML 输出

```text
reports/btc-4h-1d-direct-trend-audit-report.html
reports/btc-4h-1d-direct-trend-audit-report.md
```

## 回测 / 评估

对比：

```text
baseline: btc_timescale_judge.v2.1 module average
candidate: btc_timescale_judge.v2.2 direct evidence + radar context
```

评估指标：

```text
Rank IC
AUC / F1 for trend_accepted
Precision@TopDecile
Whipsaw Rate
False Breakout Reduction
Lead Time
Confidence Calibration
Event Window Robustness
```

回测要求：

```text
使用 walk-forward 或 purged/embargoed split。
禁止随机 K-fold 泄漏未来信息。
```

## DoD

1. 审计显示 4h / 1d direct evidence 的 metric lineage。
2. 审计显示 module contribution 只是 radar_context。
3. 审计验证 event overlay 只影响 trust_score / confirmation gate。
4. 审计验证 SQLite / API / Vue 使用同一 snapshot_id。
5. 审计显示 `direction_score / acceptance_score / trust_score / display_score`。
6. 回归案例通过：
   - short_covering 不误判为 trend_accepted
   - crowded_long 不误判强多
   - breakout rejection 能降低 4h acceptance
   - BTC residual resilience 能阻断 confirmed bearish
   - volatility shock 能压低 trust
   - pre_event 只能 trust cap，不能改变 direction
   - post_event_unconfirmed 只能 watch/building，不能 confirmed
   - post_event_accepted 才能作为事件驱动方向证据
   - hot CPI + BTC reclaim 必须输出 shock_absorbed / no confirmed bearish
7. 若 direct evidence 缺失，审计 FAIL，不允许静默 fallback 成 module average。
8. 输出 v2.1 vs v2.2 对比结论。

## 数据断层审计

P7 必须输出一张链路矩阵：

```text
metric_id
source_id
source_asof_ts
derived_at
registry_role
used_by_horizon
state_machine_input
p45_output_path
sqlite_snapshot_id
api_snapshot_id
ui_rendered_field
freshness_state
gap_status: pass|gap|stale|missing|fallback
```

审计 Fail 条件：

```text
P1 有 metric 但 P2 未注册。
P2 注册但 P3/P4.5 未消费且无 ignore_reason。
P4.5 输出 snapshot_id 与 SQLite/API/UI 不一致。
API 返回 fresh 但 source_fresh=false。
UI 展示 confirmed 但 source_fresh=false 或 acceptance_gate stale。
审计 HTML 与 latest API snapshot_id 不一致。
```
