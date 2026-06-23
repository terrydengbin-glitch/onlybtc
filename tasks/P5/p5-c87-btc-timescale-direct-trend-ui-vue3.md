# P5-C87 / BTC TimeScale Direct Trend UI Vue3

## 状态
DONE

## Execution Record

### 2026-06-22 / Start

- 前置 P9-C55 已完成，dashboard / overview / runtime cockpit 已暴露 `btc_timescale_judge.v2.2`、`btc_timescale_replay_snapshot`、`direct_trend_api`。
- 本卡目标：Vue3 时间尺度视图优先消费 v2.2 direct trend API，固定展示 4h / 1d / 3d / 7d 四张卡，并保留 v2.1 / horizon_views fallback。

### 2026-06-22 / Done

- `frontend/src/App.vue`：
  - `horizons` 固定输出 4 张卡：`4h`、`1d`、`3d`、`7d`。
  - 优先读取 `btc_timescale_judge.v2.2.horizons`，缺失时 fallback 到 `direct_trend_api.horizons`、v2.1 `24h/3d/7d`、旧 `horizon_views`。
  - 4h / 1d 卡显示 State、Direction Score、Trust、Display Score、Direct Evidence、Radar Context、BTC Acceptance、Event Trust Cap、Event Phase、Next Confirmation、Invalidation。
  - BTC 主卡的 4h / 24h 小读数改为 direct trend horizon 口径。
  - `direction_score` 控制方向样式；`trust_score` 只控制 low-trust 降级透明度；`source_fresh=false` 使用 quality 视觉，避免强确认。
  - `fallback_used/fallback_reason`、runtime fresh、source fresh 均有 badge 展示。
- `frontend/src/styles.css`：
  - 时间尺度视图改为稳定 2x2 四卡布局。
  - 新增 score grid、freshness badge、evidence chain、fallback / low-trust / warning 样式。

Verification:

```text
npm run build
vue-tsc -b && vite build passed
```

## 目标

升级时间尺度视图，让 4h / 1d 成为可见的直接趋势裁判卡，而不是隐藏在 BTC 主卡或 24h 文案里。

UI 必须展示判断链，而不是只展示分数。

## UI 布局

保留 4 张卡：

```text
4h 变盘侦测
1d / 24h 短线趋势
3d 资金 / 宏观确认
7d Regime 背景
```

4h / 1d 卡固定显示：

```text
State
Direction Score
Confidence / Trust
Display Score
Direct Evidence
Radar Context
BTC Acceptance
Event Trust Cap
Next Confirmation
Invalidation
```

## 视觉规则

1. `direction_score` 控制方向颜色。
2. `trust_score` 控制置信度/透明度/降级标识，不反向染色。
3. `event_trust_cap` 用 badge 明示。
4. `radar_context` 只显示 confirming / conflicting / degrading，不覆盖 Direct Evidence。
5. `volatility_shock / event_distorted` 必须有明显 warning 样式。

事件展示：

```text
pre_event:
  显示 trust capped，不显示方向箭头

post_event_unconfirmed:
  显示 event pressure + waiting BTC reaction，不显示 confirmed

post_event_accepted:
  显示 event-driven followthrough / shock_absorbed / trend accepted
```

## 示例文案

```text
4h：价格出现下行 impulse，但 CVD/OI 尚未完全确认，当前是 impulse_watch，不是 trend_accepted。

1d：24h 仍在 VWAP 下方，衍生品压力延续，但事件窗口压低 trust，当前为 trend_fragile。
```

## DoD

1. Vue3 优先读取 `btc_timescale_judge.v2.2`。
2. 缺失 v2.2 时 fallback v2.1 / horizon_views。
3. 4h / 1d 卡显示人话结论和证据链。
4. UI 明确区分：
   - direct trend score
   - radar context
   - event trust cap
   - data/source freshness
5. Vue3 不直接消费审计 HTML。
6. npm build 通过。
7. UI 不破坏现有 dashboard 框架。
8. Event Window 进入 4h/1d 卡时，必须显示阶段：pre_event / post_event_unconfirmed / post_event_accepted / shock_absorbed。

## UI Freshness 展示

UI 必须展示并区分：

```text
runtime fresh: daemon 是否仍在更新
source fresh: 底层 direct evidence 是否新鲜
fallback used: 当前是否回退到 v2.1/horizon_views/stale snapshot
```

交互规则：

```text
source_fresh=false 时，4h/1d 卡不得显示为强确认视觉。
fallback_used=true 时，必须显示 fallback badge。
event_trust_cap 生效时，显示 trust capped，而不是改变方向颜色。
```
