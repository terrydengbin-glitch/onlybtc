# P2-C43 / BTC 4H/1D Direct Evidence Registry

## 状态
DONE

## Execution Record

### 2026-06-22 / Start

- 前置 P1-C75 已完成，live evidence run：`p1c75-direct-20260622154526-512969`。
- 本卡目标：为 `btc_direct_trend_evidence` 产出的 feature_id 建立 role/horizon/freshness/cadence registry，并输出可审计的 registry payload。
- 边界：不改变 P4.5 裁决结果；P3/P4.5 后续通过 registry 读取角色，避免硬编码 direct evidence 语义。

### 2026-06-22 / DONE

- 新增 `onlybtc.direct_trend.registry`，提供：
  - `direct_evidence_registry()`
  - `registry_entry_for_feature(feature_id)`
  - `build_direct_evidence_registry(...)`
- 新增 CLI：`btc-direct-evidence-registry`。
- Registry module output：`module_id=btc_direct_evidence_registry`，`schema_version=p2.c43.direct_evidence_registry.v1`。
- live registry run：`p2c43-registry-20260622154808-aa0a1a`，对齐 P1 evidence run `p1c75-direct-20260622154526-512969`。
- Registry 覆盖 22/22 条 P1 direct evidence；`missing_in_latest=[]`，`unregistered_latest=[]`。
- Role counts：`trigger_eligible=4`，`acceptance_gate=5`，`radar_context=8`，`trust_cap=4`，`quality_gate=1`。
- OI / funding 单点指标全部为 `radar_context`，`affects_direction=false`，不能直接触发方向。
- Event overlay 默认 direction disabled；注册为 `trust_cap` 或 `quality_gate`，并保留 `pre_event/post_event_unconfirmed/post_event_accepted` phase roles。
- Verification：
  - `python -m pytest backend/tests/test_btc_direct_evidence_registry.py` => 2 passed
  - `python -m pytest backend/tests/test_btc_direct_trend_evidence.py backend/tests/test_btc_direct_evidence_registry.py backend/tests/test_p3_features.py backend/tests/test_p45_timescale_judge.py` => 11 passed
  - `python -m compileall backend/src/onlybtc/direct_trend backend/src/onlybtc/cli.py` => passed

## 目标

在指标注册层新增 `direct_trend_evidence` 语义，明确哪些指标可进入 4h / 1d direct judge，哪些只能作为 radar context、trust cap 或展示字段。

## Registry 分类

```text
trigger_eligible:
  可直接参与 4h turning point / 1d persistence 判断

acceptance_gate:
  判断方向是否被市场接受

trust_cap:
  只降低置信度，不改变方向

radar_context:
  只确认、冲突或降级 direct evidence

context_only:
  展示或审计，不参与方向

quality_gate:
  stale / missing / latency / provider degraded 的阻断或降级字段
```

## Event Window Role

Event Window 相关字段必须按阶段注册：

```text
pre_event:
  role = trust_cap
  不允许 trigger_eligible

post_event_unconfirmed:
  role = context_only 或 trust_cap
  可输出 event_pressure_direction，但不得触发 confirmed

post_event_accepted:
  role = trigger_eligible 或 acceptance_gate
  前提是 BTC first reaction / 30m followthrough / 2h acceptance / orderflow confirmation 全部有证据
```

事件驱动反转不能直接由事件文本触发，必须有 BTC 反应验证。

## 必须注册的组合语义

```text
price_up + oi_up + taker_buy_dominant = aggressive_long_building
price_up + oi_down = short_covering_rally
price_down + oi_up + taker_sell_dominant = aggressive_short_building
price_down + oi_down = deleveraging_drop
funding_high + price_fail_breakout = crowded_long_rejection
liquidation_spike + price_not_following = liquidation_absorption
external_pressure_bearish + residual_positive = btc_resilient
```

## Radar Context 边界

```text
radar_context_bias = clip(weighted_relevant_radar_score, -15, +15)
```

要求：

```text
Radar module 不得覆盖 direct evidence。
Radar module 只能 confirm / conflict / degrade trust / explain background。
中性 direct evidence + 强 radar context 不允许直接 confirmed。
```

## DoD

1. 4h / 1d direct evidence 不再混在普通 `horizon_tags` 里。
2. 每个 direct evidence 有 `role / horizon / freshness tier / direction semantics / source cadence`。
3. Event overlay 字段全部归类为 `trust_cap` 或 `quality_gate`，默认不影响 direction。
4. OI / funding 单点指标不能标记为 `trigger_eligible`。
5. partial depth 派生项不得标记为 OFI，只能标记为 `depth_imbalance_context`。
6. P3/P4.5 可以按 role 读取 registry。
7. 审计报告能显示每个 metric 的 role 和被 P4.5 使用/忽略原因。
8. `post_event_accepted` 才能进入 direction evidence；`pre_event` 永远只做 trust gate。

## Freshness / Cadence Registry

Registry 必须为每个 direct evidence 定义：

```text
cadence_group: fast|confirmation|regime|event|derived
expected_update_sec
stale_after_sec
blocking_level: none|degrade|block_confirmed|block_all
fallback_policy: none|use_previous_with_stale_flag|use_proxy|drop_metric
required_for:
  - 4h_direction
  - 4h_acceptance
  - 1d_direction
  - 1d_acceptance
```

门控：

```text
trigger_eligible stale => 不允许 fast_trend_acceptance。
acceptance_gate stale => 不允许 trend_accepted。
trust_cap stale => 不阻断方向，但必须降低 trust。
quality_gate blocked => horizon blocked 或降级。
```
