# P9-C31 / Onchain Valuation v2.2 API 透传与契约

## 状态

DONE

## Phase

P9 FastAPI 聚合 API 与运维质控

## 背景

前端和 P4.5 需要消费 `onchain_valuation.v2.2` 的慢快分数、动态 STH 成本位、signal stage、proxy flags 与 invalidation conditions。FastAPI 不能只透传旧的 `module_effective_direction`。

## 目标

在 radar detail、dashboard 聚合、final pack 查询中透传 v2.2 payload。

## API 契约

```json
{
  "onchain_valuation_v22": {
    "semantic_profile_version": "p3.c52.onchain_valuation.v2.2",
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
    "key_levels": {
      "realized_price": null,
      "sth_cost_basis": null,
      "sth_upper_band": null,
      "sth_lower_band": null,
      "lth_cost_basis": null
    },
    "support_drivers": [],
    "pressure_drivers": [],
    "early_warning_flags": [],
    "invalidation_conditions": [],
    "proxy_flags": [],
    "data_quality_flags": []
  }
}
```

## DoD

- [ ] Radar Detail API 透传 `onchain_valuation_v22`。
- [ ] Dashboard summary 可读取 `signal_stage` 与 `module_bias`。
- [ ] Final pack / evidence detail 可读取 key levels、proxy flags 与 invalidation conditions。
- [ ] 旧 payload 缺失时 API 不报错，返回空态兼容结构。
- [ ] FastAPI 集成测试覆盖 v2.2 字段。

## 关联任务

- P8-C26
- P4.5-C35
- P5-C52
