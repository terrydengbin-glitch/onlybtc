# P9-C30 / Fund Flow v2.2 API 透传与契约

## 状态

DONE

## Phase

P9 FastAPI 与前后端契约

## 背景

`fund_flow.v2.2` 需要在 FastAPI 层透传 P3 semantic profile 与 P4.5 explanation，供 Vue3 Dashboard、Radar Detail、History Replay 与报告页消费。

## 目标

API 输出必须包含：

```text
semantic_profile_version = p3.c50.fund_flow.v2.2
fund_flow_state
module_direction
module_score
confidence_score
btc_implication
scores
states
support_drivers
pressure_drivers
early_warning_flags
data_quality_flags
```

## API 契约

`/api/p45/radar-modules/fund_flow` 增加：

```json
{
  "fund_flow_state": "",
  "btc_implication": "",
  "fund_flow_v22": {
    "semantic_profile_version": "p3.c50.fund_flow.v2.2",
    "scores": {},
    "states": {
      "etf_demand": {},
      "stablecoin_liquidity": {},
      "exchange_supply": {},
      "btc_response_confirmation": {}
    },
    "support_drivers": [],
    "pressure_drivers": [],
    "early_warning_flags": [],
    "data_quality_flags": []
  }
}
```

Dashboard module summary 增加：

```json
{
  "radar_module": "fund_flow",
  "display_state": "fund_flow_state",
  "display_summary": "",
  "fund_flow_state": "",
  "btc_implication": "",
  "semantic_profile_version": "p3.c50.fund_flow.v2.2"
}
```

## 兼容规则

- 老 run 没有 v2.2 字段时，仍返回 P2-C23 的 `fund_flow_absolute_direction`、`fund_flow_marginal_direction`、`fund_flow_state`。
- 缺少子状态时返回空对象，不抛 500。
- `exchange_flow_untrusted` 必须在 API 层保留 data quality flags。

## DoD

- [ ] `/api/p45/radar-modules/fund_flow` 透传 v2.2 contract。
- [ ] `/api/p45/dashboard/latest` 的模块摘要可消费 v2.2 display state。
- [ ] `/api/p45/history/{final_run_id}` 可回放 v2.2 状态。
- [ ] 老 run 兼容 P2-C23/P4.5-C22 字段。
- [ ] FastAPI contract 测试覆盖 warning、confirmation、rejection、untrusted 四类状态。

## 关联任务

- P3-C48
- P4.5-C34
- P5-C51
