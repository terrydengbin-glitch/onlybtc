# P3-C14 事件窗口分析器与 Post-event 风险总结治理

## 状态

DONE

## 所属 Phase

P3 算法敏感检测与预警系统 / P1 官方宏观事件日历 / P2 Event Policy Radar / P4 Evidence Pack / P5 Dashboard

## 背景

P3-C08 已实现事件窗口倒计时预警，当前链路为：

```text
P1 official-macro-event-calendar
  -> cpi_days_until / fomc_days_until / pce_days_until / nfp_days_until
  -> P3 detect_event_windows()
  -> p3_event_window_engine feature_values
  -> event alert candidate
  -> P3 HTML Event Window Details
```

但按业务预期，脚本应在 `T-7 / T-3 / T-1 / T-0 / T+1 / T+3` 时间段主动关注事件、分析相关信息，并输出带数据的总结。当前实现仍有断层：

- P1 采集端将过去事件的 `days_until` 使用 `max(..., 0)` 压成 0，导致真实链路几乎无法进入 `T+1 / T+3`。
- `T-7` 当前只是 `info`，不会进入 alert candidate，无法形成“开始关注”的结构化总结。
- 事件 alert summary 只有 `{event_type} 距离 {days_until} 天，risk_lock={risk_lock}`，缺少事件相关数据摘要。
- `event_state_invalidation` 当前看 `macro_surprise_score / fed_speech_risk / fomc_event_risk`，没有直接消费事件窗口 `risk_lock`。
- P3 HTML 展示了 Event Window Details，但没有事件窗口分析摘要、前后窗口状态、相关 Radar/指标证据。

## 当前真实样例

2026-05-21 最近真实 run 中，事件窗口为：

```text
CPI  : 20.23 天，outside，info，risk_lock=False
FOMC : 27.46 天，outside，info，risk_lock=False
NFP  : 15.23 天，outside，info，risk_lock=False
PCE  : 8.23 天，outside，info，risk_lock=False
```

这些事件都能生成 feature rows，但尚未形成事件窗口分析总结。

## 业务目标

将 P3-C08 从“事件倒计时检测”升级为“事件窗口分析器”：

```text
official calendar + fallback calendar
  -> signed event distance / event phase
  -> event window state
  -> macro surprise / Fed speech / FOMC blackout / event_policy radar
  -> structured event summary
  -> event invalidation / alert / P4 evidence
```

P3 在事件窗口内必须能回答：

- 当前处于哪个事件窗口：`T-7 / T-3 / T-1 / T-0 / T+1 / T+3 / outside`。
- 事件是 pre-event、event-day 还是 post-event。
- 从 `T-7` 到 `T-3` 是否进入每日关注状态，每次运行是否重新检查事件相关数据变化。
- 本事件相关数据有哪些：`macro_surprise_score`、`aggregate_macro_surprise`、`fed_speech_risk`、`fomc_event_risk`、`fomc_blackout_active`、`event_policy` Radar。
- 是否触发 `risk_lock`，以及它对发布、解释强度、总控输出有什么影响。
- 事件窗口总结能否被 P4/P5 直接消费。

## 实施要求

### 1. P1 保留 signed days 或 event_phase

当前 `official-macro-event-calendar` 输出 `days_until=max(delta, 0)`，需要新增或调整为：

```yaml
event_signed_days:
  cpi_signed_days
  fomc_signed_days
  pce_signed_days
  nfp_signed_days
```

或在 raw/event metadata 中保留：

```yaml
event_phase: pre_event | event_day | post_event
signed_days: float
event_datetime
previous_event_datetime
next_event_datetime
```

要求：

- 真实链路可以进入 `T+1 / T+3`。
- 不能破坏现有 `*_days_until` 兼容字段。
- fallback 日历也必须能提供 previous/next event。

### 2. P3 事件窗口状态升级

`detect_event_windows()` 应输出更完整的 metadata：

- `event_type`
- `event_name`
- `event_datetime`
- `signed_days`
- `days_until`
- `event_phase`
- `window`
- `alert_level`
- `risk_lock`
- `window_action`
- `source_id`
- `source_run_id`
- `feature_run_scope`
- `fallback_reason`

窗口语义建议：

```text
T-7: info/watch, start_monitoring
T-3: watch, reduce_direction_confidence
T-1: warning, pre_event_risk_lock
T-0: warning/critical_candidate, event_day_risk_lock
T+1: watch/warning, post_event_reaction_check
T+3: info/watch, post_event_review
outside: info, monitor
```

### 3. 事件窗口分析摘要

P3 应为每个事件窗口生成结构化 summary：

```yaml
event_summary:
  headline
  data_points:
    macro_surprise_score
    aggregate_macro_surprise
    macro_surprise_event_count
    fed_speech_risk
    fomc_event_risk
    fomc_blackout_active
    event_policy_signal
    event_policy_confidence
  interpretation:
    risk_direction
    confidence_impact
    publish_impact
  actions:
    monitor | reduce_strong_direction_publish | require_post_event_review | block_critical_publish
```

要求：

- summary 必须包含真实数值与 source/run 信息。
- T-7 也要形成“关注型”摘要，即使不升级为 warning。
- T-7 到 T-3 必须每天关注；每次运行都要比较上次 run 的事件数据、source_resolution、fallback 状态、days/signed_days、macro surprise 与 Fed 风险数据是否变化。
- Post-event 窗口必须关注 Actual/Surprise/Fed speech 变化，而不是只看倒计时。

### 3.1 T-7 到 T-3 每日关注与变化检测

当任一事件进入 `T-7 <= signed_days <= T-3` 时，P3 必须生成每日关注记录：

```yaml
daily_watch:
  active: true
  watch_reason: pre_event_monitoring
  previous_run_id
  current_run_id
  changed_fields:
    - event_datetime
    - signed_days
    - source_resolution.status
    - fallback_used
    - macro_surprise_score
    - aggregate_macro_surprise
    - macro_surprise_event_count
    - fed_speech_risk
    - fed_speech_scheduled_risk
    - fomc_blackout_active
  change_summary
```

要求：

- 每次 run 都生成事件关注摘要，即使没有变化。
- 如果没有变化，summary 明确写 `no_material_change`。
- 如果 fallback 状态、事件日期、Fed speech risk、macro surprise 任一变化，summary 必须列出变化字段和新旧值。
- Daily watch 不一定触发 warning，但必须进入 P3 HTML 与 P4 Evidence Pack。

当前数据源支持度：

- `official-macro-event-calendar` 支持事件日期、下一次事件、source_resolution、fallback_used、raw payload hash，可用于日历变更检查。
- `metric_values` 支持按 run 比较 `*_days_until`，可用于倒计时变化检查。
- `raw_observations` 已保存 raw payload 与 `payload_hash`，可用于每次运行检测官方页面/回退日历是否变化。
- `fxstreet-economic-calendar` 支持 `macro_surprise_score / aggregate_macro_surprise / macro_surprise_event_count`，但当前更偏“已公布/日内 surprise”，不一定稳定覆盖 T-7 到 T-3 的预期变化。
- `fed-calendar`、`fed-rss-all-speeches`、`fed-rss-all-testimony`、`fed-fomc-blackout-calendar` 可支持 Fed 讲话、内容风险和 blackout 风险变化。

结论：

- 现有数据源可以支持 T-7 到 T-3 的“每日关注”和“日历/风险字段变化检测”。
- 若要做更强的“市场预期变化、共识预期、Actual/Forecast/Previous 变化”，当前数据源不完全足够，需要后续增强 FXStreet/TradingEconomics/官方 release detail 或其他经济日历源。
- `Forecast / Actual / Previous` 预期数据源增强作为第二阶段，不阻塞 P3-C14 第一阶段交付；第一阶段先完成 signed days、每日关注、变化检测、post-event review、P3 HTML 审计与 P4 evidence 可消费字段。

### 4. 事件窗口驱动反证

`event_state_invalidation` 应消费事件窗口风险：

- `T-1 / T-0` 且 `risk_lock=True`：至少 near_trigger。
- `T-0` 且宏观 surprise/Fed risk 高：triggered。
- `T+1 / T+3` 进入 post-event review，不允许强方向结论直接发布。
- payload 必须包含：
  - `event_type`
  - `window`
  - `signed_days`
  - `risk_lock`
  - `event_summary`
  - `affected_metrics`
  - `publish_impact`

### 5. Alert 与审计报告

P3 alert candidate 应支持事件窗口 summary：

- T-7 生成 info/watch 关注项。
- T-3/T-1/T-0 生成 watch/warning。
- T+1/T+3 生成 post-event review。

`reports/p3-algorithm-audit-report.html` 新增：

- Event Window Summary
- Event data points
- Pre/Post event phase
- Risk lock 与 publish impact
- Raw official/fallback source trace

## DoD

- 真实或测试数据可覆盖 `T-7 / T-3 / T-1 / T-0 / T+1 / T+3` 六类窗口。
- P1 保留 signed event distance 或等价 event_phase，不再让 post-event 被压成 0。
- P3 event window feature metadata 包含完整事件摘要与数据点。
- T-7 可进入关注队列；T+1/T+3 可进入 post-event review。
- `event_state_invalidation` 能消费事件窗口 risk_lock。
- P3 HTML 展示事件窗口分析摘要，而不只是 days_until 表。
- P4/P5 可从 P3 evidence 直接读取事件窗口总结。
- `pytest backend/tests -q` 与 ruff 通过。
- 真实跑 `scripts/p3-full-audit.ps1`，输出 P1/P2/P3 HTML，并确认事件窗口摘要可审计。

## 执行结果

2026-05-21 已完成第一阶段：

- P1 `official-macro-event-calendar` 新增 `cpi_signed_days / fomc_signed_days / pce_signed_days / nfp_signed_days`，保留原有 `*_days_until` 兼容字段。
- fallback 官方日历保留近 7 天已发生事件，使 P3 可以进入 `T+1 / T+3` post-event 窗口。
- P2 `event_policy` Radar 将 signed days 纳入 `event_context`，只影响风险/证据，不扭曲方向信号。
- P3 `detect_event_windows()` 优先使用 signed days，输出 `event_phase / window_action / event_summary / daily_watch / source_trace`。
- `event_state_invalidation` 已消费 P3 event window risk，并在 payload 中输出 `event_risk_details`。
- P3 HTML 已新增 Event Window Summary，并展示 `signed_days / daily_watch / publish_impact / source_resolution / fallback_used`。
- Forecast/Actual/Previous 预期数据源增强保留为第二阶段。

验证：

- `.\.venv\Scripts\python.exe -m pytest backend/tests -q`：74 passed。
- `ruff check ...`：通过。
- `scripts/p3-full-audit.ps1`：通过，输出：
  - `collect_run_id=collect-20260521072037-01b7cd`
  - `p2_radar_run_id=radar-20260521072205-13cbfd`
  - `p3_run_id=p3-20260521072206-c9c71c`
  - `reports/p1-c22-真实数据全链路验收报告.html`
  - `reports/p2-radar-quality-report.html`
  - `reports/p3-algorithm-audit-report.html`

2026-05-21 追加审计 HTML 排版优化：

- P3 HTML 表格增加横向滚动容器与 sticky 表头。
- `changed_fields` 等 list/dict 字段改为分行结构化展示，避免挤成一团。
- 重新运行 `scripts/p3-full-audit.ps1`，输出 `p3_run_id=p3-20260521072600-d38029`。
