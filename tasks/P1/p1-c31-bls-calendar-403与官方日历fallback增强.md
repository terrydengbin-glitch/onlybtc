# P1-C31 BLS Calendar 403 与官方日历 Fallback 增强

## 状态

DONE

## 所属 Phase

P1 数据源与历史数据底座

## 问题背景

本轮真实采集中，`official-macro-event-calendar` 可以产出 `cpi_days_until`、`nfp_days_until`、`fomc_days_until`、`pce_days_until`，但 BLS 页面请求返回 403：

```text
https://www.bls.gov/schedule/news_release/current_year.asp -> 403 Forbidden
```

这不是数据不存在，而是 BLS 对直接 HTTP 客户端访问做了拦截。浏览器路径通常会跳到年度日历页，例如：

```text
https://www.bls.gov/schedule/2026/home.htm
```

当前系统依赖 `_fallback_macro_events()` 补 CPI/NFP 日期，所以链路不阻断，但审计里应明确区分：

- 官方页面成功解析
- 官方页面 403，使用版本化官方 fallback 表
- 官方 fallback 表过期或缺失

## 解决方案

### 1. BLS 访问策略改为多层

```yaml
bls_calendar_resolution:
  primary:
    method: httpx
    urls:
      - https://www.bls.gov/schedule/news_release/current_year.asp
      - https://www.bls.gov/schedule/{year}/home.htm
    headers:
      user-agent: browser_like
      accept-language: en-US,en;q=0.9

  fallback_1:
    method: playwright_text
    url: https://www.bls.gov/schedule/{year}/home.htm
    purpose: bypass simple HTTP 403 when browser rendering works

  fallback_2:
    method: embedded_official_calendar_table
    scope: current_year
    must_include:
      - cpi
      - nfp
    status: warning_not_error
```

### 2. 审计字段增强

`official-macro-event-calendar` raw payload 增加：

```yaml
source_resolution:
  bls:
    status: http_403 | parsed | playwright_parsed | embedded_fallback
    url_attempted:
    fallback_used: true/false
    event_count:
```

Data Quality / P1-C22 中显示：

```text
BLS: HTTP 403，已使用 embedded official calendar fallback，非阻断。
```

### 3. fallback 表版本化

将 `_fallback_macro_events()` 拆为可维护结构：

```yaml
macro_calendar_fallbacks:
  year: 2026
  source_note: official release schedule manually pinned
  updated_at:
  expires_at:
```

超过 `expires_at` 后，P1-C22 必须给出高优先级问题。

## DoD

- BLS 403 不再只是一条模糊 warning，而是明确记录 fallback 层级。
- CPI/NFP 倒计时仍能稳定输出。
- 如果 Playwright 能解析 BLS 年度页，则优先使用页面真实数据。
- 如果只能用 embedded fallback，则质量分轻微扣分，但不阻断 P2/P3。
- P1-C22 HTML 中能看到 BLS 的 `fallback_used=true` 与使用原因。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode live --source-id official-macro-event-calendar
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit --no-collect-live
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check src tests
```
