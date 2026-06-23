# P1-C73 Event Window Secondary Source Throttle / Cache Guard

状态：DONE

## 背景

重启后观察到 Event Window daemon 与 API 均为 healthy，但日志中 `faireconomy-ff-calendar-thisweek-json` 连续返回：

```text
HTTP/1.1 429 Too Many Requests
```

这说明 Event Window 的二级日历源虽然已经具备 fallback / partial-live 能力，但还缺少更严格的 source-level 节流、缓存复用和退避门控。该问题不应影响 Event Window 的核心运行状态，但必须避免 UI 轮询、source status API 或 daemon tick 让低频二级源被重复抓取。

核心原则：

```text
official / mirror source 优先保持新鲜；
secondary free source 必须低频、缓存优先、429 后退避；
API / UI 默认只读 SQLite / cache，不直接触发外部抓取；
partial live 是可用状态，但不能 fake live，也不能暴力刷新。
```

## 目标

为 Event Window secondary calendar mesh 增加 provider 级 throttle / cache guard，使 `faireconomy`、`fxstreet`、`dukascopy`、`fxcm`、`tradays stub` 等免费二级源具备：

1. 最小抓取间隔。
2. 成功结果缓存 TTL。
3. 429 / 403 / timeout 后指数退避。
4. UI / API 读取路径不触发外部网络请求。
5. 审计 HTML 和 source diagnostics 能显示 throttle / cache / backoff 状态。

## 范围

仅针对 Event Window 二级数据源治理，不修改 radar score，不改变 BTC 主卡方向，不改变 official actual / official calendar 的事实确认逻辑。

## Provider 策略

```yaml
secondary_source_guard:
  faireconomy-ff-calendar-thisweek-json:
    min_interval_sec: 1800
    cache_ttl_sec: 3600
    error_backoff_sec:
      429: 7200
      403: 21600
      timeout: 1800
    use_stale_cache_when_blocked: true

  fxstreet-calendar:
    min_interval_sec: 1800
    cache_ttl_sec: 3600
    error_backoff_sec:
      403: 21600
      timeout: 1800
    use_stale_cache_when_blocked: true

  dukascopy-economic-calendar-free:
    min_interval_sec: 3600
    cache_ttl_sec: 7200
    error_backoff_sec:
      403: 21600
      timeout: 3600

  fxcm-economic-calendar-free:
    min_interval_sec: 21600
    cache_ttl_sec: 86400
    error_backoff_sec:
      403: 86400
      timeout: 21600
```

## 实现要求

1. 新增或扩展 secondary provider fetch guard：
   - 记录 `last_attempt_at`
   - 记录 `last_success_at`
   - 记录 `next_allowed_at`
   - 记录 `last_http_status`
   - 记录 `throttle_status`
   - 记录 `cache_status`
2. 当 provider 未到 `next_allowed_at`：
   - 不发起 HTTP 请求
   - 返回 `throttle_status=skipped_until_next_allowed`
   - 如有缓存，返回 `cache_status=served_cached`
3. 当 provider 返回 429：
   - 写入 `blocked_reason=rate_limited_429`
   - 设置 provider-specific backoff
   - 若有缓存，继续使用缓存并标记 `fallback_used=stale_cached_secondary`
4. 当 provider 返回 403：
   - 写入 `blocked_reason=access_denied_403`
   - 设置长退避
   - 不重复高频抓取
5. `/api/event-window/latest`、`/api/event-window/sources/status`、dashboard latest 默认只读 SQLite / last snapshot，不得触发 secondary external fetch。
6. 只有以下入口允许触发 external fetch：
   - daemon scheduler 到期 tick
   - event-window 独立 run once
   - audit bundle runner 的单次 collect_once
7. source diagnostics API 必须透传：
   - `throttle_status`
   - `cache_status`
   - `next_allowed_at`
   - `last_http_status`
   - `blocked_reason`
   - `fallback_used`
8. Event Window source audit HTML 必须显示：
   - provider 是否被 throttle
   - 是否 served cached
   - 是否处于 429 / 403 backoff
   - 下次允许抓取时间
9. 429 不应导致 Event Window 整体 `data_quality_blocked`。
10. 429 状态下 Event Window 仍允许 `partial_live`，但不得输出 fake consensus / fake actual。

## 输出契约补充

```json
{
  "provider": "faireconomy-ff-calendar-thisweek-json",
  "source_tier": "secondary_calendar_free_export",
  "status": "success|partial|failed|throttled|backoff",
  "last_http_status": 429,
  "throttle_status": "allowed|skipped_until_next_allowed|backoff_active",
  "cache_status": "fresh_cache|stale_cache|served_cached|cache_missing",
  "last_attempt_at": "",
  "last_success_at": "",
  "next_allowed_at": "",
  "blocked_reason": "rate_limited_429",
  "fallback_used": "stale_cached_secondary"
}
```

## DoD

1. [x] 连续调用 `/api/event-window/latest` 5 次，不触发 secondary calendar 外部 HTTP 请求。
2. [x] 连续调用 `/api/event-window/sources/status` 5 次，不触发 secondary calendar 外部 HTTP 请求。
3. [x] `faireconomy` 返回 429 后，后续请求在 backoff 窗口内不再访问该 endpoint。
4. [x] 429 / 403 后如有缓存，Event Window 输出 `partial_live` + `served_cached`，不降级为整体 blocked。
5. [x] 429 / 403 后如无缓存，provider 标记 `backoff` / `failed`，但 consensus / actual 不得伪造。
6. [x] source diagnostics API 显示 `throttle_status`、`cache_status`、`next_allowed_at`、`blocked_reason`。
7. [x] `event-window-source-audit-report.html` 显示 throttle / cache / backoff 状态。
8. [x] `scripts/run_event_window_audit_bundle.py` 能生成 HTML 1/2/3/4；运行中 daemon 会写入新 snapshot 时，bundle summary 可判定 STALE。
9. [x] Event Window daemon health 保持 healthy 或 partial_live；429 不触发 watchdog stale。
10. [x] 测试覆盖 secondary provider guard、API no-fetch read path、429 backoff。

## 验证记录

```text
python -m compileall backend/src/onlybtc/event_window/connectors/secondary_calendar.py backend/src/onlybtc/db/repositories.py scripts/generate_event_window_source_audit_html.py
=> passed

$env:PYTHONPATH='E:\onlyBTC\backend\src'; .\.venv\Scripts\python.exe -m pytest backend/tests/test_event_watchtower.py backend/tests/test_event_watchtower_offline.py
=> 14 passed

scripts/run_event_window_audit_bundle.py
=> generated reports/event-window-audit-bundle-summary.html/json
=> source audit HTML shows:
   - faireconomy-ff-calendar-thisweek-json: backoff_active, cache_missing, blocked_reason=rate_limited_429
   - fxstreet-calendar: skipped_until_next_allowed, served_cached
   - dukascopy-economic-calendar-free: skipped_until_next_allowed, served_cached
   - fxcm-economic-calendar-free: backoff_active, access_denied_403

注意：
audit bundle 在 daemon 常驻运行期间生成时，SQLite latest snapshot 可能被 daemon 后续 tick 更新，
因此 bundle summary 可能显示 STALE；这属于 P7-C21 同源 snapshot 门控语义，不代表 P1-C73 失败。
```
