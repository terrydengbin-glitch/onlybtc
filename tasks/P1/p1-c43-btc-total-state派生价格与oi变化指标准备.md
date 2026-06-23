# P1-C43 / BTC Total State 派生价格与 OI 变化指标准备

## 状态：DONE

## 背景

P3-C41 将 `btc_total_state` 升级为分层状态模块。第一阶段可复用既有 `btc_return_1h / btc_return_4h / btc_return_24h` 与 `btc_open_interest.change_24h`，但长期需要更清晰的 P1 派生指标，避免 P3 反复从 raw value 推导短线状态。

## 目标

为 `btc_total_state v2` 准备可复用的价格动量与 OI 变化指标：

```text
btc_1h_return_pct
btc_4h_return_pct
btc_24h_return_pct
btc_price_vs_1h_close_pct
btc_oi_change_1h_pct
btc_oi_change_4h_pct
btc_oi_change_24h_pct
btc_oi_zscore
btc_funding_band
```

## 已完成

- Binance 1h kline 派生并写入 `btc_1h_return_pct / btc_4h_return_pct / btc_24h_return_pct / btc_price_vs_1h_close_pct`。
- Funding 采集同时写入 `btc_funding_band`，用于 P3 funding band 语义回退。
- Open Interest 入库后派生并写入 `btc_oi_change_1h_pct / btc_oi_change_4h_pct / btc_oi_change_24h_pct / btc_oi_zscore`。
- 新指标进入 source metric definitions，并持久化到 SQLite `metric_values`。
- Radar registry 为新指标补充 horizon tag 与 duplicate group，避免与旧 `btc_return_1h / 4h / 24h` 重复冲突。
- `btc_total_state` radar 规则将新指标标记为 `price_state` / `perp_state`，保持 `affects_signal=false`、`driver_eligible=false`，不单独生成方向 driver。
- P3-C41 profile 读取新 OI 4h change 与 `btc_funding_band` 回退值。

## DoD

- [x] P1 稳定输出价格 return 与 OI change 派生指标。
- [x] 派生指标进入 SQLite `metric_values`，并带完整 run scope。
- [x] 与现有 `btc_return_1h / 4h / 24h` 无重复冲突，P2 已设置 duplicate group。
- [x] P1/P2/P3 相关测试通过。

## 验证

```text
.\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py backend\tests\test_radars.py backend\tests\test_p3_pipeline.py -q
83 passed
```
