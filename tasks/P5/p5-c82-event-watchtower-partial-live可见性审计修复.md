# P5-C82 / Event Watchtower Partial Live 可见性审计修复

## 背景

P7-C23 审计确认 Event Window 当前数据源是：

```text
overall_source_mode = partial
live_source_count = 11
partial_source_count = 2
fallback_source_count = 3
failed_source_count = 5
```

这是可接受状态，但 UI 必须持续明确展示，避免用户误以为 consensus / FedWatch / prediction market 全部是 official live。

## 目标

确保 Event Watchtower 子页面和 Dashboard Summary Widget 中，partial live / disabled capabilities / proxy / missing 都清晰可见。

## 修改范围

- `frontend/src/App.vue`
- `frontend/src/styles.css`

## UI 要求

在 Event Watchtower `Live` 或 `History` 页面可见：

```text
Source Mode: partial_live
Disabled:
  actual_pending
  consensus_unconfirmed
  official_surprise_disabled
  prediction_market_low_liquidity
  release_surprise_disabled
```

在 Dashboard Summary Widget 中至少展示：

```text
source mode: partial
radar trust: low/reduced/normal
```

## DoD

- [ ] Event Watchtower UI 明确显示 source mode。
- [ ] UI 显示 disabled capabilities。
- [ ] consensus missing / FedWatch missing 不显示成 official live。
- [ ] proxy / fallback 有独立视觉标记。
- [ ] 不改变 Event Window 业务状态机。
- [ ] `npm run build` 通过。

