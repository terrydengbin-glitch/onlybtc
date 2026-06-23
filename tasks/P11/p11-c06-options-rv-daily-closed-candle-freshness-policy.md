# P11-C06 / Options RV daily closed candle freshness policy

## 状态

DONE

## 背景

P11-C05 已将 `options_rv` 改为使用已收盘日 K，避免当前未收盘日 K 的未来 `source_ts`。

最新 run once 复审发现：

```text
future source_ts in latest collect = 0
options_rv.ts = 已收盘日 K close time
rv_change_1d.ts = 已收盘日 K close time
```

但 `binance-btcusdt-kline-1d-rv` 仍沿用 intraday freshness policy，可能导致已收盘日 K 在 P2/P3 中被误判为过期或缺失。

## 目标

将 `options_rv` 的 freshness / business recency 策略改为 daily closed candle 口径。

## 已完成

- 为 `binance-btcusdt-kline-1d-rv` 增加 `daily_closed_candle` freshness policy。
- 已收盘日 K 在下一根日 K 关闭前保持合理可用。
- `options_rv` 不再因默认 15 分钟 intraday 规则被误判 expired。
- 不改变 `options_volatility` v2.1 的方向隔离契约。

## DoD

- 最新 run 中 `options_rv` 可进入 `volatility_regime.basis.options_rv`。
- `options_volatility.data_quality.missing_count` 不再因 `options_rv` freshness policy 误增。
- `options_volatility` 仍满足：

```text
module_direction = neutral
module_score = 0
module_effective_score = 0
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py backend\tests\test_radars.py backend\tests\test_p3_pipeline.py backend\tests\test_p45_dashboard_api.py -q
npm run build
```
