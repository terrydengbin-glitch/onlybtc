# P5-C68 / Event Window v3 Source Status UI

## 状态

TODO

## Phase

P5 Vue3 前端

## 背景

事件子页面目前能显示 Event Window 业务状态，但无法清楚区分：

```text
live source
partial source
embedded fallback
provider failed
```

用户需要一眼确认“collector 是否真正拉到数据”。

## 目标

在事件子页面增加 Source Status 区域，并消费 P9-C43 API。

## UI 要求

```text
Source Mode:
  live / partial / fallback / failed

Source Cards:
  Fed FOMC Calendar
  Fed RSS
  BLS Calendar/API
  BEA Schedule/API
  Cleveland Fed Nowcast
  CME FedWatch / market-implied proxy
  BTC reaction source
```

## 状态颜色

```text
live: teal/green
partial: yellow
fallback: orange
failed: red
skipped: grey
```

## DoD

- [ ] 事件子页面显示整体 source mode。
- [ ] 每个 source 显示 last_attempt、last_success、status、fallback_used。
- [ ] fallback-only 时页面明确显示“当前不是 live 数据”。
- [ ] high/critical overlay 若来自 fallback-only，UI 必须显示低置信提示。
- [ ] `npm run build` 通过。

## 依赖

- P9-C43
- P8-C35

## Execution Record

- Fixed the Dashboard endpoint error cache so successful `/api/event-window/*` refreshes remove stale 500 entries from the UI.
- Covered both latest page hydration and the 15s Event Window live refresh path.
- Verified `/api/event-window/latest`, `timeline`, `calendar`, `alerts`, `daemon/status`, `sources/status`, and `sources/fetches` return 200 through the Vite proxy.
- Verified the page no longer renders the `API errors` panel after successful Event Window refresh.
