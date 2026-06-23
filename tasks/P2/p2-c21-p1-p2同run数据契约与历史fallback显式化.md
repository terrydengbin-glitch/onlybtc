# P2-C21 P1-P2 同 run 数据契约与历史 fallback 显式化

## 状态

DONE

## 所属 Phase

P2 全量雷达模块 / P1 真实采集审计 / P8 SQLite run 契约 / P3 算法敏感检测 / P4 Evidence Pack

## 背景

2026-05-21 真实执行 P2-C19 后发现一个链路断层：

```text
P1 HTML:
  collect_run_id = collect-20260521061410-f92352
  radar_run_id   = radar-20260521061605-66dda4
  本轮 source 状态: error=56, warning=4, healthy=3
  本轮 metric_values: 17 rows, 15 metrics
  失败/缺失: 107

P2 HTML:
  radar_run_id = radar-20260521061607-446956
  feature_values = 114
  missing_metric_count = 0
  low_quality_modules = []
  uncovered_metric_count = 0
```

这说明 P1/P2 不是“同一份本轮证据”在传递：

- P1-C22 在自身审计过程中先跑了一次 Radar。
- P2-C19 随后又跑了一次 Radar，导致 P1 HTML 与 P2 HTML 的 Radar run_id 不一致。
- P2 Radar 使用 `run_mode=live` 的历史窗口补齐，而不是锁定本轮 `collect_run_id`。
- 因此 P1 显示本轮真实采集大量失败，但 P2 仍可能因为历史 live 数据完整而显示全绿。

这不是 P2-C20 的指标覆盖问题，而是 P1/P2/P8 的 run 契约与历史 fallback 显示问题。

## 业务目标

P2-C19 作为全链条重跑入口，必须能回答：

- 本轮 P1 真实采集产出了多少指标？
- P2 Radar 每个 feature 是来自本轮采集，还是来自历史 live fallback？
- P1 HTML 与 P2 HTML 是否属于同一个业务 run？
- 如果 P2 使用历史数据补齐，质量报告是否明确展示并降权/提示？

## 目标链路

```text
P2-C19 command
  -> collect_sources(live) once
  -> collect_run_id
  -> P1-C22 audit consumes same collect_run_id
  -> P2 Radar consumes same collect_run_id first
  -> missing current-run feature may use explicit historical fallback
  -> P2 HTML exposes current-run vs historical-fallback split
  -> P3/P4 consume run lineage and fallback evidence
```

## 实施要求

### 1. P2-C19 只创建一个业务 collect run

- `run_p2_full_chain_audit()` 应持有本轮 `collect_run_id`。
- P1-C22 不应在 P2-C19 内部隐式创建另一个无法被 P2 继承的业务上下文。
- P1 HTML 与 P2 HTML 都必须展示同一个 `collect_run_id`。

### 2. P1-C22 Radar run 语义显式化

二选一：

- P1-C22 在 P2-C19 链路中不再额外执行 Radar，只做 P1 采集与数据质量审计。
- 或者保留 P1 内部诊断 Radar，但字段必须明确为 `p1_diagnostic_radar_run_id`，不能和 P2 主 Radar run 混淆。

### 3. P2 Radar 支持 run_scope

Radar 数据读取需要支持：

```yaml
run_scope:
  collect_run_id: collect-...
  run_mode: live
  historical_fallback: true
```

读取策略：

- 优先读取 `metric_values.run_id == collect_run_id`。
- 当前 run 缺失时，若允许 historical fallback，再读取同 `run_mode=live` 的历史窗口。
- 每个 feature 必须记录：
  - `source_run_id`
  - `feature_run_scope`: `current_run` / `historical_fallback` / `provider_required` / `missing`
  - `fallback_age_seconds`
  - `fallback_reason`

### 4. P2 HTML 新增 run 契约审计

`reports/p2-radar-quality-report.html` 必须新增：

- `collect_run_id`
- `p2_radar_run_id`
- `current_run_feature_count`
- `historical_fallback_feature_count`
- `provider_required_feature_count`
- `missing_feature_count`
- `same_run_coverage_score`
- module-level fallback table
- feature-level run_scope table

当本轮真实采集只产出少量指标时，P2 不能只显示全绿，必须把历史 fallback 作为质量风险展示。

### 5. 质量与下游影响

- 历史 fallback 不等同于当前 run 数据。
- `data_quality` 与 `confidence` 应考虑 `same_run_coverage_score`。
- P3 应能从 feature metadata 识别历史 fallback，并在 invalidation/anomaly 中保留该事实。
- P4 Evidence Pack 必须保留 `collect_run_id -> radar_run_id -> feature source_run_id` 的追溯链。

## DoD

- P2-C19 真实跑一次后，P1/P2 HTML 展示同一个 `collect_run_id`。
- P2 HTML 明确展示 P2 主 Radar run_id，与 P1 诊断 Radar run_id 不混淆。
- P2 Radar feature metadata 中包含 `feature_run_scope` 与 `source_run_id`。
- P2 HTML 展示 current-run 与 historical-fallback 数量。
- 当本轮采集缺失较多时，P2 报告不能只显示全绿，必须给出 fallback 风险提示。
- `pytest backend/tests -q` 与 ruff 通过。
- 复跑真实 `scripts/p2-full-audit.ps1`，输出 P1/P2 HTML。
- 复跑 P3 full audit，确认 P3/P4 上游 evidence 仍可追溯。

## 执行记录

2026-05-21 已完成：

- `historical_window()` 支持 `collect_run_id` 与 `historical_fallback`。
- P2 Radar 支持同 run 优先读取，并在缺失时显式使用历史 fallback。
- Radar feature metadata 已写入：
  - `source_run_id`
  - `feature_run_scope`
  - `current_run_has_value`
  - `fallback_age_seconds`
  - `fallback_reason`
- P2-C19 现在只执行一次真实采集，并把同一个 `collect_run_id` 传给 P1/P2。
- P1-C22 在 P2-C19 链路中不再额外执行诊断 Radar，HTML 显示 `P1 诊断 Radar run_id：未执行`。
- P2 HTML 新增 Run Contract，展示 current-run / historical-fallback / provider-required / missing 统计。
- 历史 fallback 会拉低 `same_run_coverage_score`，并进入 `historical_fallback_dependency` 风险说明。

验证结果：

- `pytest backend/tests -q` 通过，72 passed。
- ruff 通过。
- `scripts/p2-full-audit.ps1 -NoCollectLive` 通过。
- `scripts/p3-full-audit.ps1 -NoCollectLive` 通过。
- 真实 `scripts/p2-full-audit.ps1` 验证中，本轮 P2 不再静默全绿：
  - `collect_run_id=collect-20260521062637-1a850b`
  - `p2_radar_run_id=radar-20260521062837-ec030e`
  - `current_run_feature_count=15`
  - `historical_fallback_feature_count=95`
  - `provider_required_feature_count=4`
  - `same_run_coverage_score=0.1402`
  - `historical_fallback_risk=True`
