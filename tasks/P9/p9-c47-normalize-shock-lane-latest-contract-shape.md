# P9-C47 Normalize Shock Lane Latest Contract Shape

## 背景

P7-C23 全面审计发现：`/api/event-window/shock-lane/latest` 在 SQLite 有 shock row 时返回 raw item；在没有 raw row 时返回 payload aggregate。两种返回结构不一致，前端和审计无法稳定消费。

## 目标

统一 `/api/event-window/shock-lane/latest` 输出契约，使其始终返回 Event Window payload 中的 `shock_fast_lane` 聚合形态，并额外携带 `latest_item` 原始事件。

## 范围

- `backend/src/onlybtc/api/event_window.py`
- Event Watchtower repository/query service，如需补查询适配
- API 契约测试

## 输出契约

接口必须稳定返回：

```json
{
  "shock_fast_lane": {
    "shock_detected": false,
    "shock_type": "none|market|policy|regulatory|exchange|stablecoin|geopolitical|cross_asset|crypto_native|unknown",
    "emergency_level": "none|watch|high|critical",
    "confirmation_level": "none|rumor|single_source|multi_source|official|market_confirmed",
    "source_count": 0,
    "market_dislocation": false,
    "btc_microstructure_confirmation": false,
    "rumor_risk": false,
    "reason_codes": [],
    "evidence": [],
    "summary": "",
    "latest_item": {}
  }
}
```

## 核心要求

1. DB 有 raw shock item 时，必须把 raw item normalize 到 aggregate contract。
2. DB 没有 raw shock item 时，继续 fallback 到 latest payload 的 `shock_fast_lane`。
3. 原始 shock history 接口可以保留 raw item，不受本任务影响。
4. 字段缺失时用安全默认值，不允许前端拿到半截契约。
5. 契约里必须标明是否 `latest_item_from_sqlite`。

## DoD

1. `/api/event-window/shock-lane/latest` 永远包含 `shock_detected` boolean。
2. `/api/event-window/shock-lane/latest` 永远包含 `summary`。
3. 有 SQLite shock row 和无 SQLite shock row 两种场景都通过契约测试。
4. 前端不需要判断 raw/aggregate 两套结构。

