# P1-C59 / Event Window v3 Actual 发布轮询与 Post-Event Reaction

## 状态

DONE

## Phase

P1 数据源接入与采集层

## 当前断点

当前 `post_event_reaction` 是 `_reaction_placeholder()`：

```text
actual = null
consensus = null
surprise_z = null
btc_return_5m / 30m / 2h = null
followthrough = pending
```

因此事件发布后还不能判断 `shock_absorbed` / `followthrough`。

## 目标

在 release window 内高频轮询 official actual，并结合 BTC 市场反应生成 post-event reaction。

## 数据源

```text
official actual:
  BLS API / BLS release page
  BEA API / BEA release page
  Fed FOMC statement / SEP / minutes page

BTC reaction:
  existing Binance kline / aggTrade / derivatives metrics
  mark price / OI / funding if available
```

## 输出契约

```json
{
  "reaction_id": "",
  "event_id": "",
  "snapshot_ts": "",
  "actual": null,
  "consensus": null,
  "surprise_raw": null,
  "surprise_z": null,
  "btc_return_5m": null,
  "btc_return_30m": null,
  "btc_return_2h": null,
  "btc_realized_vol_z": null,
  "oi_change_15m": null,
  "funding_change": null,
  "btc_absorbed_shock": null,
  "followthrough": "pending|absorbed|followthrough|fakeout|blocked"
}
```

## 规则

```text
surprise_raw = actual - consensus
surprise_z = surprise_raw / historical_abs_surprise_std

hot inflation + BTC first drop but 30m recovers >= 70%
  => shock_absorbed

hawkish policy shock + BTC breaks pre-event low and fails to reclaim
  => followthrough

dovish surprise + BTC pops but CVD/OI fails
  => relief_rally_weak / fakeout
```

## DoD

- [x] release window 内不再只输出 placeholder reaction。
- [x] actual 未发布时保留 `pending`，不能伪造 actual。
- [x] actual 发布后能写入 actual / surprise_raw / surprise_z。
- [x] BTC 5m / 30m / 2h reaction 至少从现有 price/kline 指标计算。
- [x] post-event reaction 进入 Event Watchtower snapshot/repository/API 链路。
- [x] API `/api/event-window/post-event-reaction` 返回 reaction。
- [x] 单元测试覆盖 pending、actual success、surprise、absorbed、followthrough。

## 实施记录（2026-06-23 状态回填）

- 实现入口已存在：
  - `backend/src/onlybtc/event_window/connectors/actuals.py`
  - `backend/src/onlybtc/event_window/connectors/reactions.py`
  - `backend/src/onlybtc/event_window/watchtower.py`
  - `GET /api/event-window/post-event-reaction`
  - `GET /api/event-window/events/{event_id}/reaction`
- 后续任务 P1-C61、P1-C66、P1-C69、P8-C37、P9-C40 已覆盖 BLS/FRED actual fallback、secondary calendar actual、market probe 和 API 透传。
- 本次仅做任务状态回填，不修改运行代码。

## 验证记录

- `backend/tests/test_event_watchtower.py` 覆盖 pending、absorbed、followthrough 和 actual provider fallback。

## 依赖

- P1-C57
- P1-C58
- P8-C35
- P9-C40
