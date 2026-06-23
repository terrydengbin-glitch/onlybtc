# P1-C34 Business Recency 策略校准与 Provider 发布节奏治理

## 状态

DONE

## 所属 Phase

P1 数据源与历史数据底座 / P2 Radar Quality / P8 双时间戳模型

## 问题背景

全量 `P1-C22` live 审计已完成，采集失败为 0：

```text
collect_run_id = collect-20260521045638-1a7b60
source_count = 63
metric_count = 107
failure_count = 0
data_quality_status = healthy
```

但问题清单仍显示：

```text
业务时间状态：14 个指标的源数据业务时间存在滞后或过旧
```

这不是采集失败。采集层 `collection_freshness_status` 全部为 fresh，问题发生在业务数据时间语义：

```text
source client -> metric_values.ts/updated_at
  -> historical_window()
  -> compute_business_recency()
  -> P1-C22 / Radar Quality
```

当前代码已经有双时间戳模型：

- `collection_freshness_status`：本地是否刚采过
- `business_recency_status`：源数据本身是否足够新

本任务要校准的是后者。

## 当前受影响指标

### FRED / 官方日频或周频发布节奏

| metric_id | source_id | 当前状态 | 根因判断 |
|---|---|---|---|
| dxy_proxy | fred-dxy | lagging | FRED DXY 日频但可能遇到非交易日/发布滞后，且有 TradingView 实时候选 |
| bank_reserves | fred-bank-reserves | lagging | 银行储备更接近周频/官方滞后发布，不应简单按 daily 判定 |
| usdjpy | fred-usdjpy | lagging | FRED FX 序列更新不一定覆盖当前交易日，已有实时页面源可补充 |
| usdcnh | fred-usdcnh-proxy | lagging | FRED proxy 更新节奏慢于实时 FX 页面源 |
| jgb_10y | fred-jgb-10y | outdated | FRED JGB 序列明显滞后，应优先实时页面源或改为官方滞后策略 |
| ofr_fsi | ofr-fsi | lagging | OFR 官方 FSI 允许 1-3 个美国工作日滞后，当前策略仍略紧 |

### K 线窗口语义

| metric_id | source_id | 当前状态 | 根因判断 |
|---|---|---|---|
| btc_1h_open/high/low/close/volume | binance-btcusdt-kline-1h | lagging | 使用已完成 1h K 线，业务时间天然接近上一小时，不能按 10 分钟 intraday 判滞后 |

### 日更页面源 / 指数源

| metric_id | source_id | 当前状态 | 根因判断 |
|---|---|---|---|
| etf_net_flow | playwright-glassnode-asset-overview | lagging | ETF flow 日频，T+1/T+2 更新正常，需要单独 policy |
| etf_flow_7d | playwright-glassnode-asset-overview | lagging | 同上 |
| sector_heat | alternative-fear-greed | outdated | Alternative.me Fear & Greed 是日更指数，当前被当成 intraday |

## 目标

将业务时间状态从“泛化滞后/过旧”改成 provider-aware 的可解释状态：

```yaml
business_recency:
  status: current | expected_lag | lagging | outdated
  provider_cadence:
  business_calendar:
  expected_publication_lag_seconds:
  affects_radar_quality: true/false
  user_visible_note:
```

其中 `expected_lag` 表示源数据按官方节奏正常滞后，不应作为质量问题扣分。

## 修复要求

### 1. Provider 级 freshness policy 扩展

在 `SourceConfig.metadata.freshness_policy` 或统一 policy registry 中补齐：

- FRED FX / DXY：按 market daily + weekend/holiday 容忍。
- FRED weekly balance sheet / reserves：按 weekly 官方发布节奏。
- JGB / 亚洲利率：若 FRED 明显滞后，应指定实时页面源为主源，FRED 为 fallback/cross-check。
- Binance 1h K 线：新增 `hourly_closed_candle` cadence。
- Glassnode ETF flow：新增 `daily_t_plus_2` cadence。
- Alternative Fear & Greed：改为 `daily_index` cadence。

### 2. Business Recency 语义扩展

当前 `compute_business_recency()` 只有：

```text
current / lagging / outdated / unknown
```

需要支持：

```text
current / expected_lag / lagging / outdated / unknown
```

`expected_lag` 应在 P1-C22 中显示为“按发布节奏正常滞后”，并且不进入阻断问题清单。

### 3. Radar Quality 扣分调整

Radar quality 不应对 `expected_lag` 进行实质扣分。

建议：

```text
current = 1.0
expected_lag = 0.95
lagging = 0.85
outdated = 0.65
unknown = 0.75
```

### 4. P1-C22 展示调整

指标清单中保留：

- 采集新鲜度
- 业务时间状态
- provider 发布节奏
- 是否按预期滞后
- 是否影响 Radar Quality

问题清单只统计真正 `lagging/outdated`，不把 `expected_lag` 当成问题。

## DoD

- 全量 `P1-C22` 后，业务时间问题不再包含按官方节奏正常滞后的指标。
- `btc_1h_*` 不再因上一根已完成 K 线被误报为业务滞后。
- `sector_heat` 按日更指数处理，不再按 intraday 判 outdated。
- `ofr_fsi`、Glassnode ETF flow 的滞后展示为可解释状态。
- Radar quality 中 `business_recency_score` 不因 expected lag 被明显拉低。
- 测试覆盖 `official_daily`、`hourly_closed_candle`、`daily_t_plus_2`、`daily_index`。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check src tests
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit
```
