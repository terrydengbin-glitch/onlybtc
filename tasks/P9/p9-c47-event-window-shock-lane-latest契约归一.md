# P9-C47 / Event Window shock-lane/latest 契约归一

## 背景

P7-C23 全面审计发现：

```text
/api/event-window/shock-lane/latest
```

在 DB 中存在 latest shock row 时，返回的是 raw shock item shape：

```json
{
  "shock_fast_lane": {
    "shock_id": "...",
    "shock_type": "crypto_native",
    "emergency_level": "high"
  }
}
```

但完整 payload 中的 `shock_fast_lane` 是 aggregate shape：

```json
{
  "shock_detected": true,
  "shock_type": "crypto_native",
  "emergency_level": "high",
  "confirmation_level": "market_dislocation",
  "source_count": 1,
  "market_dislocation": true,
  "btc_microstructure_confirmation": true,
  "summary": "..."
}
```

这会导致 UI 或外部调用方看到 `shock_detected = null`，即使当前存在 high shock。

## 目标

统一 `/shock-lane/latest` API 契约，使其始终返回 aggregate `shock_fast_lane`，同时保留 raw latest item。

## 修改范围

- `backend/src/onlybtc/api/event_window.py`
- 可能新增 helper：
  - `_normalize_shock_fast_lane(latest_shock, fallback_payload)`

## 输出契约

```json
{
  "shock_fast_lane": {
    "shock_detected": true,
    "shock_type": "crypto_native",
    "emergency_level": "high",
    "confirmation_level": "market_dislocation",
    "source_count": 1,
    "market_dislocation": true,
    "btc_microstructure_confirmation": true,
    "rumor_risk": false,
    "reason_codes": [],
    "evidence": {},
    "summary": "",
    "latest_item": {}
  }
}
```

## DoD

- [ ] DB 有 latest shock row 时，`shock_detected=true`。
- [ ] 返回中始终有 `summary`。
- [ ] 返回中始终有 `latest_item` 保存 raw row。
- [ ] 无 shock 时返回 `shock_detected=false`，且契约字段完整。
- [ ] Event Watchtower UI 的 Shock Lane 不再因为 raw shape 显示 unknown/null。
- [ ] 后端测试覆盖 no-shock / has-shock 两种情况。

