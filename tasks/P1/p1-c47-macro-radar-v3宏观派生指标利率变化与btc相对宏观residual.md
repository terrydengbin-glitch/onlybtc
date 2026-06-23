# P1-C47 / Macro Radar v3 宏观派生指标、利率变化与 BTC 相对宏观 residual

## 状态

DONE

## 目标

为 `macro_radar.v3` 准备趋势敏感输入，使宏观模块能回答：

```text
BTC 当前 4h-3d 趋势，是否被宏观风险资产环境确认、削弱、反证，还是进入宏观冲击状态？
```

P1 只负责派生指标和历史窗口，不直接输出方向结论。

## 范围

新增或补齐以下派生指标：

```text
# equity beta
nasdaq_return_24h_pct
sp500_return_24h_pct
russell_return_24h_pct
equity_breadth_score

# rates pressure
us2y_change_1d_bps
us10y_change_1d_bps
us10y_change_3d_bps
real_yield_change_1d_bps
yield_curve_2s10s_change_bps
rates_impulse_z

# dollar pressure
dxy_change_1h_pct
dxy_change_4h_pct
dxy_change_24h_pct
dxy_impulse_z

# volatility / stress
vix_change_1d_pct
vix_change_3d_pct
vix_zscore_60d
vix_impulse_z
ofr_fsi_change_1d
ofr_fsi_zscore_252d

# btc relative confirmation
btc_return_1h_pct
btc_return_4h_pct
btc_return_24h_pct
btc_vs_ndx_relative_return
btc_vs_spx_relative_return
btc_beta_residual
btc_macro_follow_through
```

## 业务约束

- 原始宏观指标不在 P1 变成 bullish/bearish。
- 利率、美元、VIX、OFR 只生成变化率、z-score、冲击强度和可用性信息。
- `btc_beta_residual` 必须明确是相对宏观 beta 的残差，不是 BTC 独立趋势分。
- 缺失数据输出 `available=false`，不得用 0 冒充真实值。

## DoD

- `macro_radar.v3` 所需派生指标进入标准化指标链路。
- 派生指标保留 `source_ts` / `collected_at` / freshness / quality 元数据。
- 支持 24h、3d、60d、252d 等历史窗口 fallback。
- P2/P3 能按同 run 读取这些派生指标。
- 旧 `macro_radar` 指标不因本任务改变默认方向语义。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py backend\tests\test_radars.py -q
.\.venv\Scripts\python.exe -m compileall -q backend/src/onlybtc
```
