# P1-C75 / BTC 4H/1D Direct Evidence Features

## 状态
DONE

## Execution Record

### 2026-06-22 / Start

- 按用户指定顺序，在 P9-C54/P9-C56 source freshness 剩余修复审计完成后启动本卡。
- 第一阶段落点：基于现有 `metric_values` / `historical_window` 生成 P1 direct evidence `feature_values`，不改 P4.5 裁决语义。
- 本轮必须覆盖 price / orderflow / derivatives / residual / event 五类，并为每个 evidence 输出 lineage/freshness 字段。

### 2026-06-22 / DONE

- 新增 `onlybtc.direct_trend.evidence.build_btc_direct_trend_evidence` 和 CLI `btc-direct-trend-evidence`。
- P1 输出写入 SQLite `feature_values`，`module_id=btc_direct_trend_evidence`，`schema_version=p1.c75.direct_evidence.v1`。
- live run：`p1c75-direct-20260622154526-512969`。
- live 写入：22 条 evidence；分类覆盖 price_structure=2、orderflow_acceptance=3、derivatives_positioning=8、btc_residual_cross_asset=4、event_overlay_context=5。
- 每条 evidence metadata 携带 `snapshot_id/source_asof_ts/collected_at/derived_at/valid_until/cadence_group/stale_after_sec/freshness_state/source_health/upstream_metric_ids`。
- CVD / `taker_delta_quote` 已落地为 `taker_buy_sell_ratio + exchange_spot_volume` notional proxy，并在 metadata 明确标注不是 full OFI/MLOFI。
- `price_oi_interaction_state`、`residual_semantic`、`post_event_reaction_state` 已作为组合语义字段输出，P4.5 后续裁决不直接依赖单点 OI/funding/liquidation。
- Verification：
  - `python -m pytest backend/tests/test_btc_direct_trend_evidence.py` => 2 passed
  - `python -m pytest backend/tests/test_btc_direct_trend_evidence.py backend/tests/test_p3_features.py backend/tests/test_p45_timescale_judge.py` => 9 passed
  - `python -m compileall backend/src/onlybtc/direct_trend backend/src/onlybtc/cli.py` => passed

## 目标

为 `btc_timescale_judge.v2.2` 提供 4h / 1d 直接趋势证据，避免时间尺度判断只依赖 radar module 综合分二次平均。

核心定位：

```text
P1 负责采集和派生 direct evidence。
P4.5 负责裁决。
Radar module 只作为背景确认，不替代 direct evidence。
```

## 特征范围

### price_structure

```text
btc_return_5m / 15m / 1h / 4h / 24h
close_location_5m / 15m / 1h / 4h
range_expansion_z_5m / 15m / 1h / 4h
session_vwap / anchored_vwap / vwap_acceptance_duration
breakout_acceptance
failed_breakout / failed_breakdown
```

### orderflow_acceptance

```text
taker_delta_quote
taker_buy_sell_ratio
cvd_slope_z
depth_imbalance_z
mlofi_z
spread_z
```

要求：

```text
OFI / MLOFI 必须优先使用 diff depth + local book。
partial depth snapshot 只能做静态 depth imbalance，不得伪装成 OFI。
```

落地边界：

```text
本轮必须实现 CVD / taker_delta_quote。
本轮允许实现 depth_imbalance_proxy / liquidity_thinning_proxy。
本轮不强制实现 full OFI / MLOFI。
如果没有 diff depth + local book，不得输出 ofi_z / mlofi_z，只能输出 proxy 字段。
```

### derivatives_positioning

```text
oi_impulse_z_15m / 1h / 4h / 24h
price_oi_interaction_state
funding_rate_8h_equiv_z
funding_acceleration_z_24h
funding_interval_hours
liquidation_followthrough_score
liquidation_absorption_score
```

语义要求：

```text
price_up + oi_up + taker_buy_dominant = aggressive_long_building
price_up + oi_down = short_covering_rally
price_down + oi_up + taker_sell_dominant = aggressive_short_building
price_down + oi_down = deleveraging_drop
funding_high + price_fail_breakout = crowded_long_rejection
```

### btc_residual_cross_asset

```text
btc_response_z_15m / 1h / 4h / 24h
expected_return_24h
residual_24h
residual_z
residual_semantic:
  external_pressure_down_but_btc_resilient
  external_support_up_but_btc_underperforming
  risk_assets_up_but_btc_not_following
  risk_assets_down_but_btc_absorbing
```

### event_overlay_context

```text
emergency_level
ordinary_radar_trust
trade_permission_modifier
event_trust_cap
post_event_reaction_state
```

Event overlay 在 P1 只产出 trust / cap 输入，不产出默认方向分。

事件阶段输入：

```text
pre_event:
  只输出 trust_cap / confirmation_threshold_adjustment，不输出方向证据

post_event_unconfirmed:
  输出 event_pressure_direction，但只能作为 watch，不允许 confirmed

post_event_accepted:
  必须同时具备 first_reaction、30m absorption/followthrough、2h/4h acceptance、orderflow_confirmation
  才允许进入 direct evidence direction
```

## 标准化

新增 robust normalizer 输入：

```text
robust_z = clip((x - rolling_median) / (1.4826 * rolling_MAD), -4, +4)
feature_score = tanh(robust_z / 2)
```

Lookback 建议：

```text
4h: 14d ~ 30d，并按 UTC hour/session 做分桶
1d: 60d ~ 120d
macro daily: 1y if available
```

## DoD

1. 4h / 1d direct evidence 至少覆盖 price、orderflow、derivatives、residual、event 五类。
2. Fast 特征按 cadence 更新，不被 24h/7d 慢源阻塞。
3. 新增特征写入 SQLite `metric_values` 或具备明确 derived lineage。
4. 每个 direct evidence 都有 `metric_id / source_id / freshness / source_tier / upstream_metric_ids`。
5. OI / funding / liquidation 单点指标不能独立作为方向特征，必须保留组合语义字段。
6. Binance OI 历史只保留近月时，长期回测必须标记 `history_limited`。
7. P7 审计能追踪每个 direct evidence 的 source freshness 和 stale reason。
8. CVD / taker_delta_quote 是本轮必做项；full OFI / MLOFI 是后续增强项，不得伪装实现。
9. Event Window 的 post-event directional evidence 必须经过 BTC reaction validation。

## 数据连贯性补充

每个 P1 direct evidence 输出必须携带：

```text
snapshot_id
source_asof_ts
collected_at
derived_at
valid_until
cadence_group
stale_after_sec
freshness_state: fresh|stale|missing|partial|blocked
source_health
upstream_metric_ids
```

要求：

```text
fast direct evidence 不允许复用过期快源。
slow macro / event context 可以 partial，但必须显式标记 partial。
derived metric 不得只保存数值，必须保存 lineage。
```
