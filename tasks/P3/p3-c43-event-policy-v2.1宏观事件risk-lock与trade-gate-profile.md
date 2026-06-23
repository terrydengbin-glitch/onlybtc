# P3-C43 / Event Policy v2.1 宏观事件 risk lock 与 trade_gate profile

## 状态
DONE

## 背景

`event_policy` v2.1 是事件风险门控 profile。它不改变 final_direction，只输出事件阶段、risk lock、confidence adjustment 与可执行 `trade_gate`。

## Profile

新增默认 profile：

```text
p3.c43.event_policy.v2.1
```

## 输出契约

```json
{
  "module": "event_policy",
  "version": "p3.c43.event_policy.v2.1",
  "module_purpose": "event_risk_and_trade_permission",
  "module_direction": "neutral",
  "module_score": 0,
  "module_effective_score": 0,
  "affects_direction": false,
  "dominant_event_type": "fomc|cpi|nfp|pce|fed_speech|blackout|null",
  "nearest_event_type": "fomc|cpi|nfp|pce|fed_speech|null",
  "nearest_event_ts": "ISO8601|null",
  "nearest_event_hours": 0,
  "event_window_phase": "neutral|caution|hard_lock|post_digest",
  "event_risk_lock_level": "none|soft|hard",
  "penalty_channel": "event_timing_only",
  "risk_score": 0,
  "confidence_adjustment": 0,
  "trade_gate": {
    "allow_new_position": true,
    "allow_add_position": true,
    "allow_breakout_entry": true,
    "allow_market_entry": true,
    "position_size_multiplier": 1.0,
    "require_wait_until_ts": null,
    "reason_code": "EVENT_NEUTRAL"
  },
  "risk_drivers": [],
  "context_notes": [],
  "summary": ""
}
```

## 事件优先级

```text
FOMC decision / press conference
> CPI
> NFP
> PCE
> high-risk Fed speech
> blackout context
```

如果多个事件重叠：

```text
nearest_event_type = 时间最近
dominant_event_type = 风险优先级最高
risk_drivers = 保留全部命中事件
```

## Gate 规则

```text
macro data <= 24h:
  phase = caution
  allow_new_position = true
  allow_add_position = false
  allow_breakout_entry = false
  position_size_multiplier = 0.5~0.7

macro data <= 6h:
  phase = hard_lock
  allow_new_position = false
  allow_add_position = false
  allow_breakout_entry = false
  allow_market_entry = false
  reason_code = WAIT_DATA_RELEASE

macro data release + 0~30m:
  phase = post_digest
  allow_new_position = false
  reason_code = WAIT_FIRST_REACTION

macro data release + 30m~2h:
  如果 surprise 高或 BTC 5m range 高:
    继续 post_digest
  否则:
    恢复 reduce_size 或 normal
```

```text
FOMC <= 48h:
  phase = caution
  position_size_multiplier = 0.5
  allow_breakout_entry = false

FOMC <= 12h:
  phase = hard_lock
  allow_new_position = false
  reason_code = WAIT_POLICY_RELEASE
```

```text
blackout_active only:
  risk_score +5~10
  不直接降级 trade_gate

blackout_active + FOMC <= 48h:
  reduce_size

blackout_active + FOMC <= 12h:
  hard_lock
```

## Aggregation 约束

```text
module_direction = neutral
module_score = 0
module_effective_score = 0
confidence_adjustment >= -0.15
```

如果 `macro_radar` 已经 high risk，`event_policy` 优先调整 `trade_gate`，避免重复大幅扣 confidence。

## 测试矩阵

```text
case_01: CPI <= 24h => caution, no add, no breakout
case_02: CPI <= 6h => hard_lock, no new position
case_03: release + 20m => post_digest, wait first reaction
case_04: release + 90m + surprise low => normal/reduce_size
case_05: FOMC <= 48h => caution, size 0.5
case_06: FOMC <= 12h => hard_lock
case_07: blackout only => context risk, no hard lock
case_08: blackout + FOMC <= 12h => hard_lock
case_09: Fed speech <= 3h + high risk => soft/hard lock
case_10: CPI near + FOMC near => dominant_event_type follows priority, nearest_event_type follows time
```

## DoD

- P3 输出 v2.1 契约字段。
- event_policy 永远 neutral，分数为 0。
- `trade_gate` 字段可被下游直接消费。
- blackout 不单独触发强降级。
- 测试覆盖事件窗口、重叠优先级、post digest 与方向隔离。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
```
