# P1-C32 FXStreet 无 Actual 事件状态治理与 Fallback

## 状态

DONE

## 所属 Phase

P1 数据源与历史数据底座

## 问题背景

本轮真实采集中，`fxstreet-economic-calendar` 页面成功渲染并解析到了 26 条 USD 事件，但 `usable_event_count=0`。

最新 raw payload 显示：

```text
rows = 26
usable = 0
原因：
- 当前窗口内事件多为未公布，actual 为 "-"
- 部分事件有 consensus/previous，但还没有 actual
- Fed speech 事件显示 LOCKED，不适合用于 macro_surprise_score
- 当前核心关键词事件尚未产生可评分 surprise
```

因此这不是抓取失败，而是“当前没有已公布且可计算 actual-vs-consensus 的事件”。现在被标为 `warning`，容易让 UI 和 P1-C22 误解为数据源坏了。

## 解决方案

### 1. 状态拆分

把 FXStreet 结果分成三类：

```yaml
fxstreet_status:
  healthy:
    condition: page_rendered and usable_event_count > 0

  no_released_event:
    condition: page_rendered and rows > 0 and usable_event_count == 0
    meaning: 当前窗口没有已公布 actual/consensus 事件
    severity: info
    quality_score: 0.70

  parser_or_page_failure:
    condition: rows == 0 or page_error
    severity: warning/error
```

### 2. 输出诊断字段

raw payload 增加：

```yaml
diagnostics:
  total_usd_events:
  relevant_event_count:
  usable_event_count:
  unreleased_event_count:
  locked_event_count:
  next_relevant_events:
    - event_name
    - local_time
    - consensus
    - previous
```

### 3. Macro Surprise 输出语义调整

当 `usable_event_count=0` 时：

```yaml
macro_surprise_score:
  value: 0
  meaning: no_new_surprise
  should_not_trigger_alert: true
```

不能把 `0` 解读为“宏观中性结果”，只能解读为“当前没有新公布值”。

### 4. Fallback 源规划

增加后续 fallback 源任务接口，不阻塞当前任务实现：

```yaml
fallback_candidates:
  - investing_calendar_playwright
  - forexfactory_calendar_playwright
  - finnhub_economic_calendar_api_optional
```

当 FXStreet `parser_or_page_failure` 时才启用 fallback；当只是 `no_released_event` 时不需要 fallback。

## DoD

- FXStreet 页面成功但无 actual 时，不再标成笼统 warning。
- P1-C22 / Data Quality 能显示“当前无已公布可评分事件”。
- `macro_surprise_score=0` 带有 `meaning=no_new_surprise`。
- P2/P3 不会因为 FXStreet 无事件而误判宏观 surprise 为中性信号。
- 保留未来接 Investing / ForexFactory fallback 的接口位置。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode live --source-id fxstreet-economic-calendar
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit --no-collect-live
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check src tests
```
