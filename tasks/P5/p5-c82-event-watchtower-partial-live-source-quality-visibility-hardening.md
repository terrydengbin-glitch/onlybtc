# P5-C82 Event Watchtower Partial-live Source Quality Visibility Hardening

## 背景

P7-C23 全面审计确认 Event Watchtower 可以 partial live 运行，但当前 UI 需要进一步强化数据源状态表达，避免用户误以为所有 provider 都是 live official。

当前 source mesh 可能存在：

- live sources
- fallback sources
- partial sources
- failed sources
- disabled capabilities，例如 consensus missing、official surprise disabled、FedWatch proxy used

这些状态必须在 Event Watchtower 子页面和 dashboard summary widget 中清晰展示。

## 目标

让 Event Watchtower UI 明确展示 partial live / fallback / failed / disabled capability，不伪装成 fully live，也不因为部分源缺失误导用户认为系统无效。

## 范围

- Event Watchtower 子页面 source/status 区块
- Dashboard 事件窗口 summary widget
- Source diagnostics 面板

## 核心要求

1. UI 显示 source mode：
   - `fully_live`
   - `partial_live`
   - `fallback_active`
   - `degraded`
   - `blocked`
2. 显示 source counts：
   - live
   - partial
   - fallback
   - failed
3. 显示 disabled capabilities：
   - `consensus_missing`
   - `official_surprise_disabled`
   - `fedwatch_proxy_used`
   - `calendar_fallback_used`
4. 只要 failed > 0 或 disabled capabilities 非空，不允许显示类似 “all sources ok” 的绿色强成功态。
5. 不改变 Event Watchtower 现有页面骨架，只增强现有区域的信息密度和样式。

## DoD

1. Event Watchtower 子页面能看到 partial live / fallback / failed 计数。
2. Dashboard summary widget 能看到 Event Window 当前数据源模式。
3. Consensus 缺失时，UI 明确显示 release surprise disabled。
4. FedWatch 使用 proxy 时，UI 明确显示 not official CME FedWatch。
5. `npm run build` 通过。

