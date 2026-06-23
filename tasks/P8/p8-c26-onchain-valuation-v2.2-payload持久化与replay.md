# P8-C26 / Onchain Valuation v2.2 Payload 持久化与 Replay

## 状态

DONE

## Phase

P8 SQLite 持久化与历史回放

## 背景

`onchain_valuation.v2.2` 会新增 `trend_delta_score`、`regime_score`、`signal_stage`、`key_levels`、`proxy_flags`、`invalidation_conditions` 等结构化字段。SQLite 与 replay 必须完整保存，避免历史回放只剩 module direction。

## 目标

持久化并可回放完整 v2.2 payload：

```text
scores
states
key_levels
signal_stage
module_bias
proxy_flags
data_quality_flags
invalidation_conditions
```

## 范围

确保以下字段进入 radar module JSON / final evidence pack / replay：

```json
{
  "module": "onchain_valuation",
  "version": "p3.c52.onchain_valuation.v2.2",
  "module_direction": "",
  "module_bias": "",
  "module_score": 0,
  "trend_delta_score": 0,
  "regime_score": 0,
  "confidence_score": 0,
  "signal_stage": "",
  "onchain_valuation_state": "",
  "btc_implication": "",
  "scores": {},
  "key_levels": {},
  "support_drivers": [],
  "pressure_drivers": [],
  "early_warning_flags": [],
  "invalidation_conditions": [],
  "proxy_flags": [],
  "data_quality_flags": []
}
```

## DoD

- [ ] P3 输出的 v2.2 payload 完整写入 SQLite。
- [ ] history replay 可读取并还原 `signal_stage`、慢快分数和 key levels。
- [ ] 旧 run 无 v2.2 payload 时有兼容 fallback。
- [ ] proxy/data quality flags 不丢失。
- [ ] 相关 repository 查询测试通过。

## 关联任务

- P3-C49
- P9-C31
- P5-C52
