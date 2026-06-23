# P1-C39 / Binance BTC Long/Short Ratio 数据源接入与 P1 指标入链

## 状态

DONE

## 背景

当前 `btc_open_interest` 使用 Binance Futures `fapi/v1/openInterest`，只能得到 BTCUSDT 总未平仓量：

```text
openInterest = total OI
```

它不能拆出 long / short 两边。要观察衍生品多空偏斜，需要新增 Binance Futures long/short ratio 数据源，而不是修改现有 OI。

可用公开源：

```text
/futures/data/globalLongShortAccountRatio
/futures/data/topLongShortAccountRatio
/futures/data/topLongShortPositionRatio
```

当前已有 `taker_buy_sell_ratio`，但它代表主动买卖流，不等于持仓多空比例。

## 目标

新增 BTCUSDT long/short ratio 数据源，并把指标完整纳入 P1/P8 采集链路：

1. 新增全市场账户多空比。
2. 新增大户账户多空比。
3. 新增大户仓位多空比。
4. 保留 `btc_open_interest` 作为总 OI，不伪造 long OI / short OI。
5. 所有新增指标具备 `source_ts / collected_at / freshness_minutes / stale_after_minutes / is_stale`。
6. 新增指标能进入 SQLite 历史窗口和 P1 HTML 审计。

## 指标命名

```text
btc_global_long_account_ratio
btc_global_short_account_ratio
btc_global_long_short_account_ratio

btc_top_long_account_ratio
btc_top_short_account_ratio
btc_top_long_short_account_ratio

btc_top_long_position_ratio
btc_top_short_position_ratio
btc_top_long_short_position_ratio
```

## 数据源

```text
binance-btcusdt-global-long-short-account-ratio
https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=5m&limit=1

binance-btcusdt-top-long-short-account-ratio
https://fapi.binance.com/futures/data/topLongShortAccountRatio?symbol=BTCUSDT&period=5m&limit=1

binance-btcusdt-top-long-short-position-ratio
https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol=BTCUSDT&period=5m&limit=1
```

## 业务口径

- `longAccount / shortAccount` 是账户比例，不是 OI 数量。
- `longShortRatio` 是多空账户或仓位比例，不是 long OI / short OI。
- `topLongShortPositionRatio` 更接近“大户仓位偏斜”，优先用于拥挤判断。
- 总 OI 仍由 `btc_open_interest` 表示。

## SQLite / P8 对齐

- 若现有 `metric_values` 支持动态 `metric_id`，不新增迁移，只验证写入。
- 若 source registry reconciliation 需要白名单，补齐新增 source 与 metric。
- History window 必须能读取新增 ratio 的 previous/change/ma 字段。

## DoD

- [ ] P1 registry 新增 3 个 Binance long/short ratio source。
- [ ] P1 client 能解析 `longAccount`、`shortAccount`、`longShortRatio`。
- [ ] 新增 9 个 metric definition。
- [ ] P1 HTML 显示新增 source 与 metric。
- [ ] SQLite 能查询到新增 metric 的最新值和历史窗口。
- [ ] 任何文案都不把 ratio 称为 long OI / short OI。
- [ ] 数据源失败时不影响 `btc_open_interest` 总 OI。
- [ ] P1/P8 相关测试通过。

## 关联

P1-C03, P1-C08, P1-C36, P1-C38, P2-C24, P3-C34

## Completion Note

- Done: 3 Binance long/short ratio sources, 9 metrics, parser, critical retry gate.
- Verified: `test_sources.py`, `test_radars.py`, `test_p3_pipeline.py`, P4.5/API tests, frontend build.
