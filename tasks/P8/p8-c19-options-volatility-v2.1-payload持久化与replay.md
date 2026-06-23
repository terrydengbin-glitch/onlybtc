# P8-C19 / Options Volatility v2.1 payload 持久化与 replay

## 状态

DONE

## 背景

`options_volatility` v2.1 输出多层结构化 payload。历史回放与 Evidence Pack 需要读取完整结构，否则 UI 和报告会退回旧的单分数解释。

## 目标

保证以下字段在 radar output / evidence / replay 中完整保存：

```text
options_short_term_state
risk_score
confidence_adjustment
trade_permission_hint
volatility_regime
protection_demand
tail_risk
expiry_pressure
pinning_structure
data_quality
risk_drivers
context_notes
```

## DoD

- 新 run 可完整持久化 v2.1 payload。
- 旧 run 缺少 v2.1 payload 时，replay/API 降级为空结构或 legacy summary，不报 500。
- History Replay 能区分 `module_score=0` 与 `risk_score>0`。
- P8/P9 回放测试通过。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```
