# P3-C56 / Event Window v3 状态机与 Emergency Overlay

## 状态
DONE

## Phase
P3 算法层 / Event Window 状态机

## 背景

Event Window 是独立于 14 个 radar modules 的事件事实层。它不直接修改 BTC score，而是通过 Emergency Overlay 改变交易权限、普通雷达可信度和事件风险提示。

该任务定义并实现 Event Window v3 的状态机与 overlay 边界，后续 P7-C16 会对其进行第二份 HTML 审计。

## 状态优先级

```text
data_quality_blocked
> unscheduled_shock_confirmed
> event_lock
> release_surprise
> policy_repricing_shock
> fed_tone_shift
> pre_event_high_alert
> expectation_drift_watch
> calendar_monitor
> event_neutral
```

补充 post-event 状态：

```text
post_event_absorbed
post_event_followthrough
```

post-event 状态只能在 official actual / release event 已确认后进入，不允许由预期或 embedded fallback 伪造。

## Overlay 输出边界

Emergency Overlay 允许修改：

```text
trade_permission_modifier
confidence_cap
volatility_warning
ordinary_radar_trust
valid_until
reason_codes
```

Emergency Overlay 禁止直接修改：

```text
BTC module_score
btc_trend_cockpit score
radar module_score
timescale_judge score
article direction
```

## Live / Fallback 治理

```text
live official + high impact T-24h:
  emergency_level = high

fallback-only event calendar:
  emergency_level max = watch
  ordinary_radar_trust = reduced
  data_quality_flags += ["event_window_fallback_only"]

official unavailable during T-1h release window:
  event_window_state = data_quality_blocked
  ordinary_radar_trust = blocked

unscheduled shock official or multi-source confirmed:
  can override scheduled calendar states
```

## DoD

- [x] `direct_score_impact` 恒为 false。
- [x] live source 可触发 high / critical overlay。
- [x] fallback-only 不允许触发 critical，默认最高 watch。
- [x] official source unavailable 在 release window 内会 blocked。
- [x] unscheduled shock 优先级高于 scheduled calendar。
- [x] overlay 只改交易权限与 ordinary radar trust，不改 BTC / radar score。
- [x] P7-C16 将生成 state / overlay / LLM 第二审计 HTML。

## 依赖

- P1-C57
- P1-C58
- P1-C59
- P2-C40
- P8-C35

