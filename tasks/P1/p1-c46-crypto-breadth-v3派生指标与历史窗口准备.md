# P1-C46 / Crypto Breadth v3 派生指标与历史窗口准备

## 状态

DONE

## 目标

为 `crypto_breadth.v3` 准备 BTC trend anchor、Top50 breadth、TOTAL2 扩散、BTC.D/ETHBTC leadership 与 sector heat 的派生指标和历史窗口。

## 范围

新增或补齐派生指标：

```text
btc_return_4h_pct
btc_return_24h_pct
btc_return_3d_pct
btc_vol_adjusted_return_24h_z
btc_trend_state

top50_advance_pct_24h
top50_advance_pct_3d
top50_ad_line_7d_slope
top50_equal_weight_return_24h_pct
top50_cap_weight_return_24h_pct
top50_equal_minus_cap_weight_return_24h_pct

total2_return_24h_pct
total2_return_3d_pct
total2_vs_btc_return_24h_pct

btc_dominance_change_24h_pp
btc_dominance_change_3d_pp
eth_btc_return_24h_pct
eth_btc_return_3d_pct

sector_heat_change_24h
breadth_price_divergence
concentration_penalty
overheat_penalty
```

## DoD

- 派生指标进入 P1 标准化指标链路。
- 历史窗口支持 24h / 3d / 7d slope 计算。
- 缺失数据时输出 `available=false`，不得用 0 冒充真实值。
- P2/P3 能按同 run 读取这些派生指标。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py backend\tests\test_radars.py -q
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
.\.venv\Scripts\python.exe -m compileall -q backend/src/onlybtc
```
