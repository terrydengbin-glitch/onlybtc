# P1-C57 / Event Window v3 官方事件日历 Live Connector

## 状态

DONE

## Phase

P1 数据源接入与采集层

## 当前断点

当前 `backend/src/onlybtc/event_window/watchtower.py` 没有真实 HTTP/RSS/API 拉取逻辑：

```text
build_event_window_payload()
  -> _fallback_calendar()
  -> _expectation_snapshot()
  -> _default_official_text_items()
```

所以 daemon 在跑、SQLite 在落库、API 在透传，但事件日历目前来自 embedded fallback，不是 live 官方源。

## 目标

新增 Event Window 官方事件日历采集器，替换 `_fallback_calendar()` 的主路径。

必须采集：

```text
Fed:
  FOMC meeting calendar
  FOMC statement / minutes / SEP / press conference metadata
  Fed RSS speeches / testimony / press releases

BLS:
  CPI
  PPI
  Employment Situation / NFP
  JOLTS
  ECI

BEA:
  Personal Income and Outlays / PCE
  GDP
```

## 数据源优先级

```text
Tier 1 official:
  Federal Reserve official pages / RSS
  BLS release calendar / API where available
  BEA schedule / API where available

Tier 2 backup:
  existing embedded fallback only when official source fails
```

## 输出契约

```json
{
  "event_id": "",
  "event_type": "CPI|PPI|NFP|JOLTS|ECI|PCE|GDP|FOMC|FOMC_MINUTES|FED_SPEECH|FED_TESTIMONY|FED_PRESS_RELEASE",
  "importance": "low|medium|high|critical",
  "release_time_utc": "",
  "release_time_et": "",
  "release_time_local": "",
  "source_tier": "official|fallback",
  "source_url": "",
  "source_name": "",
  "title": "",
  "actual_available": false,
  "official_text_available": false,
  "fetched_at": "",
  "source_hash": "",
  "data_quality_flags": []
}
```

## 实现要求

- 新增 `backend/src/onlybtc/event_window/connectors/official_calendar.py`。
- 使用 `httpx`，设置 timeout、retry、user-agent、backoff。
- 官方源失败时才允许 fallback，并必须写入：

```text
official_calendar_unavailable
embedded_official_calendar_fallback
```

- 不允许静默把 fallback 标成 official live。
- 事件必须保留 UTC、US/Eastern、Asia/Shanghai 三种时间口径。
- `event_id` 必须稳定，避免同一事件重复落库。
- 采集结果需要写入 `event_calendar_items`，并在 snapshot 的 `data_quality_flags` 暴露源状态。

## DoD

- [x] `collect_once()` 在联网可用时不再调用 `_fallback_calendar()` 作为主路径。
- [x] `/api/event-window/calendar` 可返回 official/fallback 分层事件。
- [x] fallback 只在 official source 异常时出现，并有明确 flag。
- [x] PCE / CPI / NFP / FOMC 等 critical 事件已由 P1-C60 至 P1-C71 的官方镜像、fallback mesh 和 secondary calendar mesh 覆盖。
- [x] Fed RSS / official text 进入 Event Watchtower official text / source fetch 链路。
- [x] 单元测试覆盖 official success、official fail fallback、时间转换、event_id 稳定性。
- [x] run once 数据质量 flags 已区分 official source 与 embedded fallback。

## 实施记录（2026-06-23 状态回填）

- 实现入口已存在：
  - `backend/src/onlybtc/event_window/connectors/official_calendar.py`
  - `backend/src/onlybtc/event_window/watchtower.py`
  - `backend/src/onlybtc/api/event_window.py`
- 后续任务已完成本卡未完成部分：
  - P1-C60 至 P1-C71
  - P7-C14 / P7-C15
  - P9-C40 至 P9-C48
- 本次仅做任务状态回填，不修改运行代码。

## 验证记录

- `backend/tests/test_event_watchtower.py` 覆盖 official calendar parser / fallback / source fetch。
- API 已存在：
  - `GET /api/event-window/calendar`
  - `GET /api/event-window/sources/fetches`

## 依赖

- P8-C35
- P9-C40
- P7-C15
