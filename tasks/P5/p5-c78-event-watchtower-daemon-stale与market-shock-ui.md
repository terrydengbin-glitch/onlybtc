# P5-C78 / Event Watchtower Daemon Stale 与 Market Shock UI

## 状态
DONE

## 背景

本轮排查显示，UI 可能显示“daemon running”，但实际 latest snapshot 已经数小时未更新。事件窗口子页面需要明确展示 daemon 是否新鲜、market probe 是否新鲜、shock lane 是否有多窗口行情证据。

## 目标

在 Event Watchtower 子页面、dashboard summary widget、浮窗/警告层中增加运行时与市场冲击可视化。

## UI 展示

### Daemon Health

```text
daemon status
last tick
last full sweep
last snapshot age
last market probe
next due sources
runtime version
```

### Market Shock Lane

```text
BTC 5m / 15m / 1h / 4h / 24h
return / z-score / evidence source
market_dislocation state
shock confirmation level
ordinary radar trust
```

### Alert Behavior

```text
daemon stale => dashboard widget 黄色/红色提示
market shock high/critical => 浮窗置顶提示
critical => 居中警告层
```

## 边界

- UI 必须从 FastAPI / SQLite summary 读取，不直接消费 HTML 审计文件。
- 不得使用 mock 值填充 market shock。
- 如果没有 market probe，显示 `market_probe_missing`，不要显示稳定。

## DoD

- [x] Event Watchtower 子页面展示 daemon stale / runtime version / last_market_probe。
- [x] Dashboard summary widget 展示 stale 或 high/critical market shock。
- [x] Shock Fast Lane 卡展示多窗口 BTC return 证据。
- [x] UI 可以区分 `no shock`、`market probe missing`、`daemon stale`。
- [x] 浮窗/警告层使用真实 API 字段。
- [x] npm build 通过。

## 依赖

- P9-C46
- P1-C69
- P2-C41


