# P8-C20 / Event Policy v2.1 payload 持久化与 replay

## 状态
DONE

## 背景

`event_policy` v2.1 输出结构化 `trade_gate` 与事件窗口字段。历史回放、Evidence Pack、API 与 UI 都需要读取完整 payload，否则会退回旧的倒计时/单分数解释。

## 目标

保证以下字段在 radar output / evidence / replay 中完整保存：

```text
semantic_profile_version
module_purpose
dominant_event_type
nearest_event_type
nearest_event_ts
nearest_event_hours
event_window_phase
event_risk_lock_level
penalty_channel
risk_score
confidence_adjustment
trade_gate
risk_drivers
context_notes
summary
```

## 兼容策略

- 新 run 必须完整持久化 v2.1 payload。
- 旧 run 缺少 v2.1 字段时，replay/API 降级为空结构或 legacy summary，不得 500。
- History Replay 必须区分 `module_score=0` 与 `risk_score>0`。
- `trade_gate` 缺字段时使用安全默认值，但必须标记 degraded。

## DoD

- P8 可持久化并回放 event_policy v2.1 payload。
- P9/API 读取旧 run 和新 run 均不报错。
- Evidence Pack 可消费 `trade_gate`。
- 回放测试覆盖 legacy payload 缺字段场景。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```
