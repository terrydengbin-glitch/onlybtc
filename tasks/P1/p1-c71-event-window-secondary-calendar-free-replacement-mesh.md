# P1-C71 Event Window Secondary Calendar Free Replacement Mesh

## 状态

DONE

## Phase

P1 数据源接入与采集层

## 背景

P1-C66 已经建立 secondary calendar mesh，但当前运行环境中以下 HTML 源存在 403、Cloudflare、重定向或页面结构不稳定问题：

```text
forex-factory-calendar
myfxbook-calendar
investing-calendar
```

这些源不应继续被硬抓，也不应被包装成 live consensus / actual 主源。Event Window 需要升级为免费可用源组合：

```text
ForexFactory HTML -> Faireconomy weekly JSON export
Myfxbook / Investing HTML -> Tradays free calendar stub + Dukascopy / FXStreet / FXCM crosscheck
```

核心原则：

```text
secondary source 可以触发 watch / high alert；
但 official actual 没确认前，不允许输出 final release_surprise。
Event Window 可以 partial live，但不能 fake live。
```

## 目标

新增和重排免费 secondary calendar provider：

```text
primary_schedule_forecast:
  faireconomy-ff-calendar-thisweek-json

keep_and_improve:
  fxstreet-calendar

provider_stub:
  tradays-calendar-free

crosscheck:
  dukascopy-economic-calendar-free
  fxcm-economic-calendar-free

disabled:
  forex-factory-calendar
  myfxbook-calendar
  investing-calendar
```

## Provider 契约

### 1. Faireconomy weekly JSON

```yaml
source_id: faireconomy-ff-calendar-thisweek-json
source_tier: secondary_calendar_free_export
status: active
replaces:
  - forex-factory-calendar
endpoint: https://nfs.faireconomy.media/ff_calendar_thisweek.json
coverage: current_week
provides:
  - schedule
  - impact
  - forecast
  - previous
missing:
  - actual
notes:
  - date 字段必须按 offset-aware datetime 解析
  - 不允许作为 actual 主源
```

### 2. FXStreet public calendar

```yaml
source_id: fxstreet-calendar
source_tier: secondary_consensus_actual_free_crosscheck
status: keep_and_improve_parser
provides:
  - schedule
  - event_description
  - official_report_link
  - forecast_crosscheck
  - actual_fast_crosscheck
notes:
  - 只使用 public calendar 页面
  - 不使用 protected API
```

### 3. Tradays free calendar

```yaml
source_id: tradays-calendar-free
source_tier: secondary_consensus_actual_free
status: provider_stub
preferred_access:
  - mt5_mql5_calendar_bridge
  - low_frequency_widget_crosscheck
provides_if_bridge_available:
  - schedule
  - importance
  - previous
  - forecast
  - actual
hard_rule:
  - 没有稳定后端或 MT5 bridge 时，不得输出 fake actual
```

### 4. Dukascopy / FXCM crosscheck

```yaml
source_id: dukascopy-economic-calendar-free
source_tier: secondary_consensus_actual_free_crosscheck
status: active_optional

source_id: fxcm-economic-calendar-free
source_tier: secondary_consensus_free_crosscheck
status: active_optional
```

### 5. Disabled HTML providers

```yaml
disabled:
  - source_id: forex-factory-calendar
    replacement: faireconomy-ff-calendar-thisweek-json
    disabled_reason: cloudflare_html_unstable

  - source_id: myfxbook-calendar
    replacement: tradays-calendar-free
    disabled_reason: 403_or_cloudflare_challenge

  - source_id: investing-calendar
    replacement: tradays-calendar-free
    disabled_reason: 403_or_html_scrape_unstable
```

## 实现要求

1. 禁用 `forex-factory-calendar` HTML provider，不再抓 `forexfactory.com/calendar`。
2. 新增 `faireconomy-ff-calendar-thisweek-json` provider：
   - `Accept: application/json`
   - 解析 `title`、`country`、`date`、`impact`、`forecast`、`previous`
   - 输出统一 event hit / forecast candidate / previous candidate
3. `date` 必须 offset-aware 解析，统一输出 UTC 与 America/New_York。
4. `faireconomy` 没有 `actual` 字段时，不允许填充 `actual_fast`。
5. 禁用或降级 `myfxbook-calendar`、`investing-calendar`：
   - source fetch 仍可输出 disabled record
   - 不再高频 HTTP 抓取
   - lineage 必须显示 replacement 与 disabled_reason
6. 保留并增强 `fxstreet-calendar` parser：
   - event keyword 命中
   - forecast / previous / actual_fast 尽量结构化提取
   - 失败时输出 parser_partial，不静默吞掉
7. 新增 `tradays-calendar-free` provider stub：
   - 明确 status=`provider_stub`
   - 没有 bridge 时不得输出 fake actual / fake consensus
8. 新增 `dukascopy-economic-calendar-free` 与 `fxcm-economic-calendar-free` crosscheck：
   - 可以低频抓取
   - 只作为 crosscheck，不作为唯一 confirmed consensus
9. consensus 只有至少两源接近时才标记：

```text
secondary_confirmed
```

10. 单一源 forecast / consensus 只能标记：

```text
secondary_unconfirmed
```

11. actual 没有 official 或两源确认时，只能输出：

```text
actual_fast_unconfirmed
```

12. audit HTML 必须显示：
   - replacement
   - source_tier
   - disabled_reason
   - fallback_used
   - consensus_status
   - actual_fast_status

## 输出契约

```json
{
  "secondary_calendar_mesh": {
    "event_id": "",
    "event_type": "",
    "secondary_calendar_status": "available|partial|unmatched|missing",
    "consensus": null,
    "consensus_status": "secondary_confirmed|secondary_unconfirmed|missing",
    "consensus_sources": [],
    "actual_fast": null,
    "actual_fast_status": "confirmed|actual_fast_unconfirmed|missing",
    "calendar_hits": [],
    "providers": [
      {
        "provider": "faireconomy-ff-calendar-thisweek-json",
        "source_tier": "secondary_calendar_free_export",
        "status": "success|partial|failed|disabled|provider_stub",
        "replacement_for": "forex-factory-calendar",
        "disabled_reason": null,
        "fallback_used": false,
        "warning": "secondary_source_not_official"
      }
    ],
    "source_lineage": []
  }
}
```

## DoD

1. [x] `forex-factory-calendar` HTML 被禁用，新增 `faireconomy-ff-calendar-thisweek-json`。
2. [x] `myfxbook-calendar` / `investing-calendar` 被禁用或降级，不再作为 live HTML 主抓取源。
3. [x] `fxstreet-calendar` parser 保留并增强。
4. [x] `tradays-calendar-free` provider stub 存在，并明确没有稳定后端时不得输出 fake actual。
5. [x] `dukascopy-economic-calendar-free` / `fxcm-economic-calendar-free` crosscheck provider 存在。
6. [x] consensus 至少两源接近才标记 `secondary_confirmed`。
7. [x] actual 没有 official 或两源确认时只能 `actual_fast_unconfirmed`。
8. [x] audit HTML 显示 replacement、source_tier、disabled_reason、fallback_used。
9. [x] FastAPI source diagnostics 透传 secondary provider replacement 状态。
10. [x] `scripts/run_event_window_audit_bundle.py` 通过。

## 验证记录

```text
pytest backend/tests/test_event_watchtower_offline.py -> 4 passed
npm run build (frontend) -> passed
scripts/run_event_window_audit_bundle.py -> overall_status PASS

snapshot_id: evt-20260528094902-9a0975de
faireconomy-ff-calendar-thisweek-json: success, parsed_item_count=1
consensus_status: secondary_unconfirmed
actual_fast_status: missing
disabled_providers: myfxbook-calendar / forex-factory-calendar / investing-calendar
```

## 依赖

- P1-C66 Event Window v3.2 Secondary Calendar Scraper Mesh
- P3-C58 Event Window v3.2 Provider Confidence Resolver
- P5-C70 Event Window v3.2 Provider Mesh UI v2
- P7-C21 Event Window HTML 1/2/3 同源 Snapshot 审计 Runner
