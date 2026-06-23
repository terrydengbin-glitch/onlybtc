# P8-C25 / Fund Flow v2.2 payload 持久化与 replay

## 状态

DONE

## Phase

P8 SQLite、历史数据与持久化

## 背景

`fund_flow.v2.2` 会新增多窗口 ETF 指标、稳定币 liquidity regime、交易所供给数据质量 flag、BTC response residual 与四类子状态。P8 需要保证这些结构在 SQLite、history replay、module_json_outputs、feature_values 中可以稳定持久化和回放。

## 目标

确保以下 payload 可持久化、可回放、可 API 查询：

```text
fund_flow_state
btc_implication
scores
states.etf_demand
states.stablecoin_liquidity
states.exchange_supply
states.btc_response_confirmation
support_drivers
pressure_drivers
early_warning_flags
data_quality_flags
```

## 范围

- `module_json_outputs` 保存完整 P2/P3 fund_flow v2.2 payload。
- `feature_values.metadata_json` 保存 scored module 的 v2.2 semantic profile。
- history replay 能按历史 final_run_id 还原 v2.2 状态。
- 旧 v1/P2-C23 fund_flow payload 缺字段时保持兼容。

## 兼容规则

```text
if semantic_profile_version != p3.c50.fund_flow.v2.2:
  use existing fund_flow_state / absolute_direction / marginal_direction fallback

if states missing:
  API returns empty child states instead of failing

if scores missing:
  use module_score and confidence only
```

## DoD

- [ ] 最新 run 的 P2/P3 `module_json_outputs` 可查询完整 v2.2 payload。
- [ ] `feature_values` 中 `fund_flow.scored_module` 保存 v2.2 profile。
- [ ] History replay 能还原 fund_flow v2.2 状态。
- [ ] 老历史 run 不因缺少 v2.2 字段报错。
- [ ] SQLite 查询和 P4.5 evidence pack 不丢失四个子状态。

## 关联任务

- P3-C48
- P9-C30
