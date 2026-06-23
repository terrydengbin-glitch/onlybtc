# P9-C37 BTC Trend Cockpit API 透传

状态：DONE

## 目标

FastAPI 在 dashboard、overview、history replay 入口稳定透传同一份 `btc_trend_cockpit.v2` payload。

覆盖入口：

```text
/api/p45/dashboard/latest
/api/p45/overview/latest
/api/p45/history
```

如项目实际路由命名不同，以现有 dashboard/latest、btc overview、history replay API 为准。

## 透传规则

1. 优先返回 `final_payload.btc_trend_cockpit`。
2. 缺失时返回 `{}`，不影响旧前端。
3. 不在 API 层重算趋势。
4. API 层不解释 raw metric。
5. history replay 返回历史 run 对应 cockpit。

## DoD

1. dashboard latest API 返回 `btc_trend_cockpit.schema_version = p45.btc_trend_cockpit.v2`。
2. overview latest API 返回同一份 cockpit。
3. history replay API 返回历史对应 cockpit。
4. 旧 payload 缺失 cockpit 时 API 不 500。
5. P9 API targeted pytest 通过。
