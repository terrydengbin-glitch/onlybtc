# P3-C61 Radar Module Freshness State Machine

状态：TODO

## 背景

主链条分频后，模块不再同步刷新。BTC 主卡必须知道每个模块是 fresh、stale、missing、blocked 还是 partial_live。

## 目标

为每个 radar module 增加 freshness state machine。

## 状态

```text
fresh
partial_live
stale
missing
blocked
degraded
```

## 裁决规则

```text
fresh: 可完整参与主卡聚合
partial_live: 可参与，但 confidence 打折
stale: 不允许作为确认证据
missing: 不参与聚合
blocked: 可触发主卡降级
degraded: 参与但降低 confidence
```

## DoD

1. 每个 module 输出 freshness_state。
2. 每个 module 输出 data_quality_flags / stale_reason。
3. confirmed_signal 必须只使用 fresh 或 partial_live 合格证据。
4. stale confirmation module 不允许升级 confirmed。
5. stale regime module 不允许覆盖 fast signal。
6. 输出 conflict/stale 对 BTC cockpit 的影响解释。
