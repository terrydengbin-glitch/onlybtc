# P1-C42 / Trade Structure 5m-15m Price Response 派生指标接入

## 状态

DONE

## 背景

P3-C37 会把 `trade_structure_flow` 升级为短线交易结构复合状态模块，其中 `price_response_state` 是关键确认层。

当前第一版可复用 Kline 1h 派生指标，但 1h 对 taker 买卖盘响应不够敏感。为了判断：

```text
taker 强买后价格是否跟涨
taker 强卖后价格是否跟跌
主动买盘是否被吸收
主动卖盘是否被承接
```

需要补充 5m / 15m 级别的价格响应派生指标。

## 目标

从 Binance BTCUSDT Kline 或已有短周期行情源生成 5m / 15m price response 派生指标，并纳入 P1 collect payload。

## 新增指标

```text
btc_return_5m
btc_return_15m
btc_close_position_5m
btc_close_position_15m
btc_range_expansion_z_5m
btc_range_expansion_z_15m
btc_volume_zscore_5m
btc_volume_zscore_15m
btc_flow_price_efficiency_5m
btc_flow_price_efficiency_15m
```

## 计算口径

```text
return = close / previous_close - 1
close_position = (close - low) / (high - low)
range_expansion_z = current_range vs recent range window zscore
volume_zscore = current_volume vs recent volume window zscore
flow_price_efficiency = abs(price_return) / abs(net_taker_pressure)
```

若 `high == low` 或缺少窗口数据：

```text
close_position = null
score input marked unavailable_or_neutral
pipeline 不得崩溃
```

## 影响范围

- P1 Binance kline source / derived metrics
- P1 audit report 指标数量与 freshness 展示
- P2/P3 后续读取这些派生指标

## 不改范围

- 不修改 P4.5 决策逻辑
- 不修改 Dashboard 展示
- 不改变现有 1h Kline 派生指标

## DoD

- P1 collect payload 能输出 5m / 15m price response 派生指标。
- 指标具备 `source_ts`、`collected_at`、freshness 字段。
- 缺少短周期数据时安全降级，不阻断全链条。
- P1 audit 能区分原始采集指标与派生指标。
- 单元测试覆盖 high == low、缺少历史窗口、正常计算三种情况。

## 验收

在一次真实 run 中，至少能看到：

```text
btc_return_5m
btc_return_15m
btc_close_position_5m
btc_close_position_15m
```

并且 P3-C38 可以消费这些字段计算 `price_response_state`。

## Execution Notes

- 新增 `binance-btcusdt-kline-5m` 与 `binance-btcusdt-kline-15m` P1 source，复用 Binance kline REST 数据。
- 新增 5m / 15m price response 派生指标：
  - `btc_return_5m`
  - `btc_return_15m`
  - `btc_close_position_5m`
  - `btc_close_position_15m`
  - `btc_range_expansion_z_5m`
  - `btc_range_expansion_z_15m`
  - `btc_volume_zscore_5m`
  - `btc_volume_zscore_15m`
  - `btc_flow_price_efficiency_5m`
  - `btc_flow_price_efficiency_15m`
- `_binance_kline_result` 已按 source metadata 的 `kline_interval` / `kline_suffix` 参数化，1h 既有指标保持兼容。
- 短周期 source 使用独立 closed-candle freshness policy，P1 historical window 可继续输出 `source_ts` / freshness 字段。
- 缺少窗口、零 range、零标准差时安全降级为 neutral 数值，不阻断 pipeline。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py -q
```

结果：`44 passed`。
