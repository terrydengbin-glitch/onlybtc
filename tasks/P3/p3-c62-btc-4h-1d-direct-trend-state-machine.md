# P3-C62 / BTC 4H/1D Direct Trend State Machine

## 状态
DONE

## Execution Record

### 2026-06-22 / Start

- 前置 P1-C75 / P2-C43 已完成。
- 输入：`btc_direct_trend_evidence` feature rows + `btc_direct_evidence_registry` role/freshness gates。
- 输出目标：新增 `btc_direct_trend_state_machine` payload，先供 P4.5/API/UI 后续接入，不替换现有 `p45.btc_timescale_judge.v2.1`。

### 2026-06-22 / DONE

- 新增 `onlybtc.direct_trend.state_machine.build_direct_trend_state_machine`。
- 新增 CLI：`btc-direct-trend-state`。
- State machine output：`module_id=btc_direct_trend_state_machine`，`schema_version=p3.c62.direct_trend_state_machine.v1`。
- 阈值集中在 `DEFAULT_THRESHOLDS`，并支持调用方覆盖。
- 输出包含 `direction_score / acceptance_score / trust_score / display_score`、4h/1d state、`freshness_summary`、`missing_evidence/stale_evidence/blocked_evidence/source_fresh`。
- Event overlay 只压 `trust_score`，不直接修改 `direction_score`；修复了 `post_event_reaction_state=0` 被误当 trust cap 的问题。
- live state run：`p3c62-state-20260622155135-9d8cba`，输入 evidence run `p1c75-direct-20260622154526-512969`，registry run `p2c43-registry-20260622154808-aa0a1a`。
- live state：4h=`range_chop`，1d=`range_compression_before_expansion`，`source_fresh=true`，blocked/stale/missing 均为空。
- Verification：
  - `python -m pytest backend/tests/test_btc_direct_trend_state_machine.py` => 5 passed
  - `python -m pytest backend/tests/test_btc_direct_trend_evidence.py backend/tests/test_btc_direct_evidence_registry.py backend/tests/test_btc_direct_trend_state_machine.py backend/tests/test_p3_features.py backend/tests/test_p45_timescale_judge.py` => 16 passed
  - `python -m compileall backend/src/onlybtc/direct_trend backend/src/onlybtc/cli.py` => passed

## 目标

新增 4h / 1d 直接趋势状态机，把 direct evidence 转换为交易化状态，而不是只输出综合分。

## 分数结构

```text
direction_score   -100..+100
acceptance_score     0..100
trust_score          0..100
display_score = direction_score * trust_score / 100
```

状态机输入：

```text
direct_evidence_score
evidence_agreement
conflict_score
event_trust_cap
liquidity_trust_cap
data_quality_score
radar_context_bias
regime_trust
```

## 4h 状态

```text
impulse_watch
breakout_testing
fast_trend_acceptance
fast_trend_rejection
absorption_after_sweep
liquidity_grab_reversal
range_chop
volatility_shock
event_distorted
```

触发原则：

```text
impulse_watch:
  price impulse 出现，但 orderflow / OI / VWAP acceptance 不足

fast_trend_acceptance:
  abs(direction_score) >= 60
  trust_score >= 65
  至少 3 类 direct evidence 同向

fast_trend_rejection:
  突破/跌破失败，价格回到 range 内，orderflow 反向

volatility_shock:
  realized_vol_z / spread_z / liquidation_shock_z 异常，trust 被压低
```

## 1d / 24h 状态

```text
trend_building
trend_accepted
trend_fragile
trend_rejected
pullback_in_uptrend
bounce_in_downtrend
macro_event_capped
crowded_long_risk
crowded_short_risk
range_compression_before_expansion
```

触发原则：

```text
trend_building:
  4h accepted，但 24h acceptance 尚未完成

trend_accepted:
  24h price acceptance + derivatives persistence + residual 同向

trend_fragile:
  price trend 存在，但 funding/OI/macro/residual 出现冲突

macro_event_capped:
  event overlay 降低 trust，方向分保留但不可强确认
```

## Event-driven Reversal Gate

事件驱动反转必须分阶段处理：

```text
pre_event:
  state 只能降级为 macro_event_capped / event_distorted / watch
  不允许改变 direction_score

post_event_unconfirmed:
  事件产生方向压力，但 BTC reaction 未验证
  只能进入 impulse_watch / trend_building

post_event_accepted:
  first reaction + 30m followthrough/absorption + 2h/4h acceptance + orderflow confirmation 同向
  才允许推动 fast_trend_acceptance / trend_accepted

shock_absorbed:
  事件方向压力出现，但 BTC 收回冲击且 residual 反向
  必须阻断 confirmed，并输出 btc_resilient / shock_absorbed
```

## DoD

1. 4h strong but acceptance weak => `impulse_watch`，不允许 `fast_trend_acceptance`。
2. breakout + negative CVD / OI followthrough weak => `fast_trend_rejection`。
3. macro/event active => `trust_score` capped，不直接修改 `direction_score`。
4. external pressure bearish + BTC residual positive => 输出 `btc_resilient` 语义。
5. realized_vol_z / spread_z / liquidation_shock_z 异常时输出 `volatility_shock` 或降低 trust。
6. 状态机输出可被 P4.5 / API / UI 直接消费。
7. 阈值必须可配置，不能散落硬编码。
8. 事件驱动反转必须通过 `post_event_accepted` gate；事件前只允许 trust cap。

## Freshness Gate

状态机必须消费 P2 registry 中的 freshness 门控：

```text
if trigger_eligible stale:
  fast_trend_acceptance -> impulse_watch / low_confidence

if acceptance_gate stale:
  trend_accepted -> trend_building / trend_fragile

if quality_gate blocked:
  horizon state -> blocked
```

状态机输出必须包含：

```text
missing_evidence
stale_evidence
blocked_evidence
freshness_summary
source_fresh: true|false|partial
```
