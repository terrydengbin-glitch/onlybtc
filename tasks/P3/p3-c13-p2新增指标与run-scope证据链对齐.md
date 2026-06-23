# P3-C13 P2 新增指标与 run-scope 证据链对齐

## 状态

DONE

## 所属 Phase

P3 算法敏感检测与预警系统 / P2 Radar 全量指标覆盖 / P1 真实采集审计 / P8 SQLite run 契约 / P4 Evidence Pack

## 背景

P2-C20 与 P2-C21 已改变 P2 到 P3 的上游证据形态：

- P2-C20 将 28 个原本未进入 Radar 的采集指标全部归入 P2 Radar。
- `RadarMetricRule` 新增 `role / affects_signal / affects_confidence / affects_risk_flags`。
- P2-C21 将 P2 Radar feature 标记为 `current_run / historical_fallback / provider_required / missing`。
- P2 HTML 已输出 `same_run_coverage_score`、`historical_fallback_feature_count` 与 `historical_fallback_risk`。

当前 P3 仍主要按旧链路工作：

- `run_p3_pipeline()` 会自行调用 `analyze_radars(run_id=p3_run_id, run_mode=...)`，没有继承 P2-C19/P2-C21 的 `collect_run_id`。
- `calculate_p3_features()`、`detect_anomalies()`、`detect_divergences()` 直接按 `run_mode` 读取历史窗口，尚未传递 `collect_run_id / historical_fallback / feature_run_scope`。
- `check_module_invalidations()` 虽读取同 run `module_json_outputs`，但尚未稳定识别 `historical_fallback_dependency`、`same_run_coverage_score` 和 P2 新增指标角色。
- P3 审计 HTML 目前不展示 P2/P3 的 run-scope 覆盖关系。

这会导致：P2 已能识别“本轮采集 vs 历史 fallback”，但 P3 的异常、背离、反证和告警仍可能把历史 fallback 当作普通 live 证据处理。

## 业务目标

P3 必须从“历史窗口算法层”升级为“带 run-scope 的证据敏感层”：

```text
P1 collect_run_id
  -> P2 Radar feature_run_scope / metric role
  -> P3 feature / anomaly / divergence / invalidation
  -> P4 Evidence Pack
```

P3 要能回答：

- 哪些 P3 feature 来自本轮采集，哪些来自历史 fallback？
- P2 新增的 context/audit/risk/event 指标是否被 P3 正确降敏或转为证据说明？
- 当 `same_run_coverage_score` 较低时，P3 是否降低异常/背离/告警敏感度？
- P4 是否可以从 P3 evidence 追溯到 `collect_run_id -> radar_run_id -> source_run_id -> metric_id`？

## 实施要求

### 1. P3 接收 P2 run contract

`run_p3_pipeline()` 需要支持：

```yaml
collect_run_id: collect-...
p2_radar_run_id: radar-...
historical_fallback: true
```

要求：

- P3 full audit 调用 P2-C19 后，必须把 `collect_run_id` 传入 P3。
- P3 内部 Radar 运行必须继承同一个 `collect_run_id`，或直接消费 P2 已产出的主 Radar run。
- P3 HTML 必须展示 P2/P3 run lineage。

### 2. P3 feature/anomaly/divergence 携带 run-scope

以下输出 metadata 必须包含：

- `collect_run_id`
- `source_run_id`
- `feature_run_scope`
- `current_run_has_value`
- `fallback_age_seconds`
- `fallback_reason`
- `same_run_coverage_score` 或 module-level equivalent
- `run_mode`
- `non_production`

涉及模块：

- `p3_feature_engine`
- `p3_anomaly_engine`
- `p3_divergence_engine`
- `p3_event_window_engine`

### 3. P2 新增指标角色进入 P3 语义

P2-C20 新增的指标角色不能在 P3 中一律当作同等敏感信号：

- `primary_signal`：可进入异常、背离、方向反证。
- `supporting_context`：可进入证据摘要和置信度修正，不应单独触发强告警。
- `risk_context`：进入风险 flags、反证说明、event/window 风险。
- `audit_context`：用于一致性校验和证据链追溯，不应触发方向性异常。
- `quality_context`：影响质量/置信度，不应直接改变方向。
- `event_context`：进入事件窗口和发布风险。

### 4. Historical fallback 反证治理

P3 必须识别 P2 的 fallback 依赖：

- 当 module `same_run_coverage_score < 0.8` 时，模块级 data quality invalidation 至少 `near_trigger`。
- 当 `same_run_coverage_score < 0.5` 时，强告警应降级或阻断 critical publish。
- `historical_fallback_feature_count` 与 affected metrics 必须写入 invalidation payload。
- `reason_code` 建议新增：
  - `historical_fallback_dependency`
  - `low_same_run_coverage`
  - `context_metric_no_directional_trigger`

### 5. P3 审计 HTML 扩展

`reports/p3-algorithm-audit-report.html` 必须新增：

- P2/P3 run lineage：
  - `collect_run_id`
  - `p2_radar_run_id`
  - `p3_run_id`
- P3 run-scope summary：
  - `current_run_feature_count`
  - `historical_fallback_feature_count`
  - `provider_required_feature_count`
  - `missing_feature_count`
  - `same_run_coverage_score`
- anomaly/divergence/event feature 表展示 `feature_run_scope`。
- invalidation 表展示 fallback reason / affected metrics。

## DoD

- P3 full audit 能继承 P2-C19 的 `collect_run_id`。
- P3 产出的 feature/anomaly/divergence/event metadata 包含 run-scope 字段。
- P3 module invalidation 能识别 `historical_fallback_dependency` 与低 same-run 覆盖。
- P2 context/audit 指标不会错误触发方向性异常或强告警。
- P3 HTML 展示 P2/P3 run lineage 与 run-scope summary。
- `pytest backend/tests -q` 与 ruff 通过。
- 真实跑 `scripts/p3-full-audit.ps1`，输出 P1/P2/P3 HTML，并确认 P3 报告能解释 P2-C20/P2-C21 后的新证据链。

## 执行记录

2026-05-21 已完成：

- `run_p3_pipeline()` 支持 `collect_run_id / p2_radar_run_id / historical_fallback`。
- P3 内部 Radar、feature、anomaly、divergence、event window 均继承 `collect_run_id` 与 historical fallback 策略。
- P3 feature metadata 已写入：
  - `collect_run_id`
  - `source_run_id`
  - `feature_run_scope`
  - `current_run_has_value`
  - `fallback_age_seconds`
  - `fallback_reason`
  - `same_run_coverage_score`
- P3 module invalidation 已识别：
  - `historical_fallback_dependency`
  - `low_same_run_coverage`
- P3 HTML 新增：
  - Run Lineage
  - Run Scope Summary
  - feature 表中的 `source_run_id / feature_run_scope / fallback_reason`
- 新增回归测试：P3 同一 run 内同时存在 current-run feature 与 historical fallback feature 时，metadata 与 module invalidation 正确表达。

验证结果：

- `pytest backend/tests -q` 通过，73 passed。
- ruff 通过。
- `scripts/p3-full-audit.ps1 -NoCollectLive` 通过。
- 真实 `scripts/p3-full-audit.ps1` 通过并输出 P1/P2/P3 HTML：
  - `collect_run_id=collect-20260521065526-d156fe`
  - `p2_radar_run_id=radar-20260521065653-49371c`
  - `p3_run_id=p3-20260521065653-f1ddf4`
  - P3 run scope: `current_run_feature_count=1124`，`historical_fallback_feature_count=10`，`provider_required_feature_count=4`，`same_run_coverage_score=0.9877`
