# P1-C29 TradingView 实时宏观市场数据源

## 状态

DONE

## 实施结果

- 已新增 6 个 TradingView 实时主源：`sp500`、`dow_jones`、`russell_2000`、`gold`、`wti_oil`、`brent_oil`。
- 已新增 4 个 FRED fallback/cross-check 源：`fred-sp500`、`fred-dow-jones`、`fred-wti-oil`、`fred-brent-oil`。
- 已接入 SQLite 标准契约：`run_id`、`source_id`、`metric_id`、`ts`、`quality_score`、freshness policy 均可落库并被 `historical_window()` 消费。
- 已配置多源仲裁：实时判断优先 TradingView，FRED 作为日线 fallback / cross-check，不会因为 FRED 官方质量分更高而抢占实时主源。
- 已完成 mock 测试、source registry 测试、freshness policy 测试和 live 采集验证。

## 本轮 live 验收

```text
run_id: collect-20260520171657-17a990
collected: 10
errors: 0
data_quality: healthy

selected primary:
- sp500 -> playwright-tradingview-sp500
- dow_jones -> playwright-tradingview-dow-jones
- russell_2000 -> playwright-tradingview-russell-2000
- gold -> playwright-tradingview-gold
- wti_oil -> playwright-tradingview-wti-oil
- brent_oil -> playwright-tradingview-brent-oil

fallback/cross-check:
- sp500 -> fred-sp500
- dow_jones -> fred-dow-jones
- wti_oil -> fred-wti-oil
- brent_oil -> fred-brent-oil
```

## P1-C22 复跑验收

```text
run_id: collect-20260520172242-518de9
radar_run_id: radar-20260520172400-b5226e
指标数量: 107
失败数量: 0
问题数量: 4
HTML: reports/p1-c22-真实数据全链路验收报告.html
```

新增指标在 `reports/p1-c22-指标参数清单.md` 中均显示为：

- SQLite：已写入
- 采集新鲜度：新鲜
- 业务时间状态：正常
- 角色：主源
- 所属雷达：macro

残留的多源冲突主要来自 TradingView 实时值与 FRED 日线值的口径/更新时间差异，不阻断 P1-C29，通过 P2-C17 / P5 Evidence 展示继续处理。

## 来源

用户确认以下指标更适合实时或准实时展示，不希望只依赖 FRED 日频数据：

```text
S&P 500
Dow Jones
Russell 2000
Gold 黄金
WTI Oil
Brent Oil
```

这些指标将用于 P2 宏观雷达升级，并在 Dashboard 上体现实时外部风险环境。

## 所属 Phase

P1 数据源与历史数据底座 / P2 宏观雷达 / P8 SQLite / P5 Dashboard

## 目标

新增 TradingView Playwright 实时/准实时宏观市场数据源，以 TradingView 页面采集为主源，FRED 日频数据作为历史/fallback/cross-check。

## 指标清单

| 指标 | metric_id | TradingView 建议 symbol / URL | FRED fallback |
|---|---|---|---|
| S&P 500 | `sp500` | `https://www.tradingview.com/symbols/SPX/` 或 `TVC-SPX` | `SP500` |
| Dow Jones | `dow_jones` | `https://www.tradingview.com/symbols/DJ-DJI/` 或 `TVC-DJI` | `DJIA` |
| Russell 2000 | `russell_2000` | `https://www.tradingview.com/symbols/TVC-RUT/` | 待验证 FRED / fallback |
| Gold 黄金 | `gold` | `https://www.tradingview.com/symbols/TVC-GOLD/` 或 `OANDA-XAUUSD` | FRED 黄金日频待验证 |
| WTI Oil | `wti_oil` | `https://www.tradingview.com/symbols/TVC-USOIL/` | `DCOILWTICO` |
| Brent Oil | `brent_oil` | `https://www.tradingview.com/symbols/TVC-UKOIL/` | `DCOILBRENTEU` |

## 数据源角色

```yaml
source_strategy:
  primary:
    source: tradingview_playwright
    role: realtime_primary
    cadence: intraday
    refresh_minutes: 10

  fallback:
    source: fred_api
    role: daily_history_fallback
    cadence: daily

  cross_check:
    source: fred_api
    use_for:
      - sanity_check
      - historical_window
      - source_conflict_evidence
```

## SQLite / 数据契约要求

每个采样必须符合 P1/P8 已建立的数据契约：

```yaml
metric_value:
  metric_id: sp500
  source_id: playwright-tradingview-sp500
  run_id: collect-...
  value: 6800.12
  ts: observed_at
  created_at: collected_at
  updated_at: collected_at
  quality_score: 0.70
  timeframe: spot
```

`historical_window(metric_id)` 必须返回：

- `observed_at`
- `collected_at`
- `collection_freshness_status`
- `business_recency_status`
- `freshness_policy`
- `candidates`
- `conflict`
- `selected_reason`

## Freshness Policy

TradingView 实时市场数据按 `intraday` 处理：

```yaml
freshness_policy:
  cadence: intraday
  expected_update_seconds: 600
  collection_stale_after_seconds: 1200
  collection_expired_after_seconds: 3600
  business_calendar:
    equities: us_market_hours
    commodities: market_hours_or_24x5
```

FRED fallback 按 `daily` 处理，不用于实时闪动，但用于历史趋势和兜底。

## Playwright 抓取要求

- 复用 P1-C06 Playwright 页面抓取框架。
- 复用现有 TradingView parser 逻辑；若 symbol 页面结构差异，补 selector fallback。
- 每个源必须有 mock payload 和 parser 单测。
- 如果 TradingView 页面反爬/失败：
  - source status = warning/error
  - 使用 FRED fallback
  - P1-C22 HTML 报告中可见失败原因

## 数据质量要求

TradingView 页面数据属于 `page_snapshot` / `realtime_primary`，质量分不应高于官方 API：

```yaml
quality_score:
  tradingview_playwright: 0.70 ~ 0.78
  fred_fallback: 0.95 but daily
```

实时判断优先 TradingView，历史稳定性和冲突校验优先 FRED。

## P1-C22 审计要求

P1-C22 复跑后，指标参数清单必须出现：

- `sp500`
- `dow_jones`
- `russell_2000`
- `gold`
- `wti_oil`
- `brent_oil`

并显示：

- 数据源 ID
- SQLite 状态
- 采集新鲜度
- 业务时间状态
- 多源仲裁角色
- 是否被 `macro_radar` 消费

## DoD

- 6 个指标均完成 TradingView 主源配置。
- 至少 WTI / Brent / S&P 500 具备 FRED fallback。
- 所有指标可写入 SQLite `metric_values`。
- `historical_window()` 能正确返回主源、fallback、冲突信息。
- P1-C22 HTML 报告可展示这些指标。
- 采集失败时不阻断全链路，能自动降级到 fallback。
- 测试覆盖：
  - TradingView parser 成功。
  - TradingView 失败 fallback 到 FRED。
  - freshness policy 使用 intraday。
  - P1-C22 能识别和展示新指标。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode live --source-id playwright-tradingview-sp500
..\.venv\Scripts\python.exe -m onlybtc.cli metric-window sp500
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit
..\.venv\Scripts\python.exe -m pytest
```
