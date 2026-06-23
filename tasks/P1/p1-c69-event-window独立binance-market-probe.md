# P1-C69 / Event Window 独立 Binance Market Probe

## 状态
DONE

## 背景

本轮漏报排查发现，Event Window 的 shock lane 依赖主业务链路里的 BTC 价格点或派生指标。主 P1 虽然在暴跌期间采到了 `btc_return_1h`、`btc_return_4h`、`btc_return_24h`，但 Event Window 自身没有独立拉取行情，也没有稳定消费这些派生指标。因此主链有数据，不代表事件窗口一定会触发预警。

## 目标

为 Event Window daemon 增加独立轻量行情探针，使它在主 radar pipeline 不运行或延迟时，仍能发现 BTCUSDT 的快速下跌、异常波动、OI/资金费率等市场冲击。

## 数据源

优先使用公开、低成本、可高频的 Binance USD-M Futures / Spot API：

```text
BTCUSDT ticker / mark price
1m / 5m / 15m kline
open interest
funding / premium index
可选：forceOrder snapshot、bookTicker
```

## 输出字段

```json
{
  "market_probe_id": "",
  "collected_at": "",
  "symbol": "BTCUSDT",
  "source": "binance",
  "price": 0,
  "returns": {
    "5m": 0,
    "15m": 0,
    "1h": 0,
    "4h": 0,
    "24h": 0
  },
  "realized_vol": {
    "5m": null,
    "15m": null,
    "1h": null
  },
  "open_interest": null,
  "funding_rate": null,
  "source_lineage": [],
  "data_quality_flags": []
}
```

## 关键要求

1. Event Window market probe 必须独立于主 P1 collector。
2. probe 失败必须进入 source lineage，不允许静默 fallback。
3. 如果 Binance 被限流，允许降频和使用最近一次 fresh snapshot，但必须标记 stale。
4. market probe 作为 shock lane 的 primary 行情源；主 P1 指标只作为 fallback。

## DoD

- [x] daemon tick 可独立获取 BTCUSDT 最新价格与 5m/15m/1h/4h return。
- [x] 主 P1 pipeline 不运行时，Event Window 仍能产生 market probe snapshot。
- [x] 每次 probe 写入 SQLite 或 Event Window payload lineage。
- [x] `/api/event-window/daemon/status` 显示 `last_market_probe_at` 和 freshness。
- [x] Binance 失败时返回 `market_probe_failed`，不伪装为无冲击。
- [x] smoke 测试覆盖 successful probe、provider failure、stale fallback。

## 依赖

- P9-C45
- P8-C37


