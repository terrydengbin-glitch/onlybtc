# P1-C16 免费宏观 Surprise 数据源与评分引擎

## 状态

DONE

## Closure（2026-06-23）

P1-C16 免费宏观 surprise 主线已完成：FXStreet 免费页面采集、本地 surprise 评分、指标落库、FastAPI 查询入口与 P2 `event_policy` 消费链路均已落地。

- 主源链路：`fxstreet-economic-calendar` 负责公开日历值，系统本地计算 `raw_surprise`、`normalized_surprise`、`weighted_surprise`、`hawkish_dovish`、`btc_impact_bias`。
- 已接入 API：`/api/macro/events/upcoming`、`/api/macro/events/{event_id}`、`/api/macro/surprise/latest`、`/api/macro/surprise/history`。
- Investing / ForexFactory / Finnhub / FMP 属于 fallback/provider upgrade，不阻塞免费主源版本完成。
- 当前窗口没有 USD 核心事件 actual/consensus 时输出 0 分和 warning，这是事件型数据的正常边界，不是任务未完成。

## 当前进度（2026-05-20）

已完成第一版 FXStreet 免费页面采集与本地 surprise 评分链路：

| 项目 | 状态 | 说明 |
|---|---|---|
| `fxstreet-economic-calendar` source | DONE | 已接入 Source Registry，使用 Playwright 渲染 FXStreet Economic Calendar |
| 页面解析 | DONE | 可解析 `country`、`event_name`、`actual`、`deviation`、`consensus`、`previous` |
| 本地评分 | DONE | 已实现 `raw_surprise`、`normalized_surprise`、`weighted_surprise`、`hawkish_dovish`、`btc_impact_bias` |
| 指标落库 | DONE | 已新增 `macro_surprise_score`、`aggregate_macro_surprise`、`macro_surprise_event_count` |
| P2-C14 消费 | DONE | `event_policy` 雷达已改为消费 `macro_surprise_score`，正值按偏鹰/偏空处理 |
| FastAPI 查询入口 | DONE | 已新增 `/api/macro/events/upcoming`、`/api/macro/events/{event_id}`、`/api/macro/surprise/latest`、`/api/macro/surprise/history` |
| Live 采集 | PARTIAL | 2026-05-20 实测 FXStreet 页面可渲染并解析 22 条 USD 事件；当前窗口暂无可用 USD 核心事件 actual/consensus，因此输出 0 分并标 warning |
| fallback 源 | TODO | Investing / ForexFactory / Finnhub / FMP 尚未接入 |

### 本轮验证结果

- `ruff check src tests`：通过。
- `..\.venv\Scripts\python.exe -m pytest`：26 passed。
- `collect-sources --mode mock --source-id fxstreet-economic-calendar`：通过，3 个 metric 落库。
- `collect-sources --mode live --source-id fxstreet-economic-calendar`：通过，页面成功渲染并落库；因当前无可用 USD 核心公布值，source health 为 warning。
- `analyze-radars`：14 个雷达完成，P2-C14 未阻塞。
- FastAPI macro 查询入口已接入现有 P8 raw/metric 表，不新增重复 SQLite 表。

## 所属 Phase

P1 数据源与历史数据底座

## 任务定位

把 `macro_surprise_score` 从“只能等商业 provider”拆成可落地的免费优先方案：

- 官方日历负责事件倒计时、发布时间、事件类型。
- 公开经济日历负责采集 `actual`、`forecast/consensus`、`previous`、`importance`。
- 本地算法计算 `raw_surprise`、`normalized_surprise`、`weighted_surprise`。
- LLM 只负责解释“偏鹰/偏鸽、risk-on/risk-off、对 BTC 的含义”，不能替代数值计算。

本任务只解决免费/低成本路径，不购买 Trading Economics、FXStreet API、Consensus Economics 等商业数据。

## 背景判断

真正免费、稳定、官方公开的“现成 macro surprise score”很少，但公开的 `actual vs forecast/consensus` 数据源足够构建一个可用的自研 surprise engine。

系统要的不是机构级宏观研究终端，而是在 CPI、PCE、NFP、ISM、Retail Sales、FOMC、Fed 讲话等事件发生时，快速知道：

- 是否超预期。
- 超预期幅度有多大。
- 偏鹰还是偏鸽。
- 对美元、利率、风险资产、BTC 是支持还是压制。

## 数据源分层

| 层级 | 数据源 | 作用 | 状态策略 |
|---|---|---|---|
| 官方日历 | BLS、BEA、Federal Reserve | 事件时间、倒计时、事件名称 | 继承 P1-C15 `official-macro-event-calendar` |
| 免费页面主源 | FXStreet Economic Calendar | `actual`、`consensus`、`previous`、`impact`、deviation ratio | 优先 Playwright 实测 |
| 免费页面 fallback | Investing.com Economic Calendar | `actual`、`forecast`、`previous`、importance | 作为 FXStreet 失败后的 fallback |
| 免费页面 fallback | ForexFactory Calendar | `actual`、`forecast`、`previous`、impact | 交易员口径交叉验证 |
| 低成本 API 可选 | Finnhub Economic Calendar | JSON `actual`、`forecast`、`previous` | 需要用户配置 API key，可选 |
| 低成本 API 可选 | FMP Economic Calendar | JSON `actual`、`forecast`、`previous` | 需要用户配置 API key，可选 |
| 商业升级 | Trading Economics、FXStreet API、Consensus Economics | 专业 consensus、历史 surprise、实时 API | 进入 P10 Provider Settings，不阻塞免费版 |
| 聚合指数参考 | Citi Economic Surprise Index 页面/替代公开页 | 宏观 regime 参考，不是单事件 surprise | 可后续作为辅助指标 |

## 指标设计

### 标准事件值

```yaml
macro_event_value:
  event_id: cpi_2026_06
  event_type: cpi
  country: US
  release_time: 2026-06-10T08:30:00-04:00
  source: fxstreet
  actual: 0.4
  forecast: 0.3
  consensus: 0.3
  previous: 0.2
  unit: percent_mom
  importance: high
  collected_at: 2026-06-10T20:30:05+08:00
  data_quality: high
```

### Surprise 计算输出

```yaml
macro_surprise_score:
  event_id: cpi_2026_06
  event_type: cpi
  raw_surprise: 0.1
  normalized_surprise: 1.35
  importance_weight: 1.0
  weighted_surprise: 1.35
  hawkish_dovish: hawkish
  btc_impact_bias: bearish
  confidence: 0.72
```

### 聚合输出

```yaml
aggregate_macro_surprise:
  window: 30d
  score: -0.45
  regime:
    - usd_negative
    - yield_down
    - risk_on
    - btc_supportive
  source_mix:
    official_calendar: high
    public_calendar_values: medium
    provider_api: none
```

## 计算逻辑

### 基础公式

```text
raw_surprise = actual - forecast
normalized_surprise = raw_surprise / rolling_std(event_type, lookback=24 releases)
weighted_surprise = normalized_surprise * importance_weight
```

### 方向解释规则

不同事件的方向不能一刀切。必须按事件类型建立解释表。

| 事件类型 | 高于预期通常含义 | 对 BTC 初步解释 |
|---|---|---|
| CPI / Core CPI | 通胀更热，降息概率下降，美元/收益率上行 | 偏空 |
| PCE / Core PCE | 通胀更热，Fed 更谨慎 | 偏空 |
| NFP | 就业更强，软着陆与高利率并存 | 轻度偏空或分歧 |
| Unemployment Rate | 失业率更高，经济走弱，降息预期升温 | 短期偏多但衰退风险升 |
| ISM PMI | 增长更强 | 视通胀环境决定 |
| Retail Sales | 消费更强，利率预期上行 | 偏空 |
| FOMC Statement / Dot Plot | 比市场预期更鹰 | 偏空 |
| Powell Speech | 鹰派措辞增强 | 偏空 |

### 置信度折扣

```yaml
confidence_discounts:
  source_disagreement: -0.10
  missing_forecast: -0.25
  stale_value: -0.15
  page_parse_low_quality: -0.20
  event_direction_ambiguous: -0.10
```

## 采集实现要求

### 1. Source Registry

新增数据源：

```yaml
sources:
  fxstreet-economic-calendar:
    method: playwright
    refresh_policy:
      normal: 1d
      event_window: 1m
    fields:
      - event_name
      - actual
      - consensus
      - previous
      - impact
      - deviation_ratio

  investing-economic-calendar:
    method: playwright
    refresh_policy:
      normal: 1d
      event_window: 1m
    fallback_for:
      - fxstreet-economic-calendar

  forexfactory-economic-calendar:
    method: playwright
    refresh_policy:
      normal: 1d
      event_window: 1m
    fallback_for:
      - fxstreet-economic-calendar

  finnhub-economic-calendar:
    method: rest_api
    api_key_env: FINNHUB_API_KEY
    optional: true

  fmp-economic-calendar:
    method: rest_api
    api_key_env: FMP_API_KEY
    optional: true
```

### 2. Event Window 调度

事件窗口内提高采集频率：

| 时间窗口 | 采集频率 | 目的 |
|---|---|---|
| T-7d 到 T-1d | 每天 1 次 | 确认事件时间和 forecast |
| T-24h 到 T-1h | 每小时 1 次 | 更新 forecast/consensus |
| T-60m 到 T+30m | 每 1 分钟 | 捕捉 actual 发布 |
| T+30m 到 T+24h | 每小时 1 次 | 处理 revision 与来源交叉验证 |

### 3. 数据标准化

- 统一事件 ID：`{event_type}_{release_date}`。
- 统一单位：`percent_mom`、`percent_yoy`、`k_persons`、`index_level`、`bps`。
- 统一时区：源站时间转 UTC，再展示为系统时区。
- 数值必须保留原始字符串与标准化数值，避免 `%`、`K`、`M` 解析误差。

### 4. Fallback 与冲突处理

```yaml
fallback_policy:
  primary: fxstreet
  fallback_1: investing
  fallback_2: forexfactory
  optional_api:
    - finnhub
    - fmp
  conflict_rule:
    same_event_actual_diff:
      threshold: 0.02
      action: mark_conflict_and_lower_confidence
    forecast_diff:
      threshold: 0.05
      action: keep_all_forecasts_and_use_weighted_consensus
```

## FastAPI / SQLite / P2 对接

### SQLite

需要落库：

- `macro_events`：事件日历与倒计时。
- `macro_event_values`：actual/forecast/previous/importance 原始与标准化值。
- `macro_surprise_scores`：单事件 surprise 计算结果。
- `source_health`：页面抓取成功率、延迟、字段缺失率、冲突率。

如现有 P8 表已覆盖，优先复用，不新增重复表。

### FastAPI

需要 API：

```text
GET /api/macro/events/upcoming
GET /api/macro/events/{event_id}
GET /api/macro/surprise/latest
GET /api/macro/surprise/history?event_type=cpi&days=180
```

### P2 雷达消费

P2-C14 事件政策、Fed 言论与宏观事件冲击雷达消费：

- `cpi_days_until`
- `pce_days_until`
- `nfp_days_until`
- `fomc_days_until`
- `macro_surprise_score`
- `aggregate_macro_surprise`
- `hawkish_dovish`
- `btc_impact_bias`

P2-C02 宏观雷达可消费：

- `aggregate_macro_surprise`
- `usd_risk_bias`
- `yield_risk_bias`

## LLM 使用边界

LLM 不计算 surprise 原始分数。LLM 只在 evidence pack 里拿到结构化数据后做解释：

```yaml
llm_input:
  event:
    type: CPI
    actual: 0.4
    forecast: 0.3
    previous: 0.2
    weighted_surprise: 1.35
  market_context:
    dxy_change_15m: 0.3
    us10y_change_15m_bps: 7
    btc_change_15m: -1.2
  task:
    - explain_hawkish_or_dovish
    - explain_btc_impact
    - list_invalidation_conditions
```

LLM 输出必须引用 event value 与市场反应，不允许只给主观判断。

## UI 对接说明

不新增独立 UI 页面，先接入已有页面：

- Dashboard 主拓扑页：事件/政策节点显示最近 surprise 与下一事件倒计时。
- BTC Detail Overview：关键驱动因素中展示宏观 surprise。
- Evidence 证据页：展示 actual/forecast/previous、来源、计算公式。
- Alerts 预警页：事件窗口触发预警。
- History Replay：回放事件公布后 1h/24h/72h 的 BTC 反应。
- Settings：可配置 Finnhub/FMP/Trading Economics 等可选 API key。

## 与其他任务关系

### 前置依赖

P1-C06、P1-C07、P1-C08、P1-C09、P1-C15、P8-C03、P8-C04、P8-C09、P8-C10。

### 下游依赖

P2-C02、P2-C14、P3-C08、P4 Evidence Pack、P5 Dashboard / Evidence / History Replay、P10 Provider Settings。

### 与 P1-C15 的边界

P1-C15 已补官方事件倒计时。本任务继续补“事件公布值与预期值”，并把 `macro_surprise_score` 从纯 provider-required 调整为“免费可做 proxy/exact-lite，商业源可升级”。

## DoD

- 至少完成 FXStreet / Investing / ForexFactory 中 1 个免费页面源的真实采集。
- 至少能对 CPI、PCE、NFP、FOMC 中 2 类事件生成 `actual/forecast/previous` 标准化结果。
- 能计算并落库 `macro_surprise_score`。
- source health 能记录字段缺失、页面失败、来源冲突。
- P2-C14 能消费 `macro_surprise_score`，且缺失时降级为“仅事件倒计时”，不阻塞全流程。
- mock/fixture 覆盖：
  - 高于预期 CPI。
  - 低于预期 NFP。
  - forecast 缺失。
  - 多源冲突。
  - 页面抓取失败 fallback。

## 验收命令

```powershell
python -m onlybtc.cli collect-sources --mode live --source-id fxstreet-economic-calendar
python -m onlybtc.cli analyze-radars
python -m pytest
```

如果免费页面源因反爬失败，任务不能直接标 DONE；必须至少保留 mock、fallback、source health 和明确的 provider upgrade 路径。
