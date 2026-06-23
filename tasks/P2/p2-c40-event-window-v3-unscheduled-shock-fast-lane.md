# P2-C40 / Event Window v3 Unscheduled Shock Fast Lane Live Connector

## 状态

DONE

## Phase

P2 事件冲击识别层 / Event Window 独立突发通道

## 背景

Event Window v3 已经具备 scheduled calendar、expectation drift、Fed speech analyzer、state machine、emergency overlay、SQLite replay、API 和前端展示。

当前 `shock_fast_lane` 的链条还不完整：

- `watchtower.py` 已支持 `unscheduled_shock_confirmed`，且 critical shock 优先级高于 scheduled calendar。
- `/api/event-window/shock-lane/latest` 已能透传 latest shock。
- 前端独立子页面和浮窗已能展示 shock fast lane 字段。
- `backend/src/onlybtc/event_window/connectors/shock_lane.py` 已有 BTC 5m return 的 market shock 雏形。

但仍存在断点：

- official shock collector 尚未系统接入 Fed / SEC / Treasury / exchange official announcements。
- market shock 仍主要依赖固定 BTC 5m return 阈值，缺少 volatility-adjusted、OI、liquidation、cross-asset confirmation。
- high shock 还没有完整进入 state machine / alert / UI 闭环。
- 单一 rumor / low confidence source 的降级规则需要测试覆盖。

## 目标

建立独立于 scheduled calendar 的突发冲击通道：

```text
official source shock
+ market dislocation shock
+ crypto-native official shock
+ cross-asset propagation shock
=> normalized shock item
=> severity classifier
=> state machine / overlay
=> SQLite / API / frontend alert
```

核心原则：

```text
Event Window 不直接修改 BTC score。
Shock Fast Lane 只改变 emergency_level、trade_permission_modifier、ordinary_radar_trust 和 alert visibility。
```

## 输入契约

每个 shock item 必须归一化为：

```json
{
  "shock_id": "",
  "detected_at": "",
  "shock_type": "policy|regulatory|exchange|stablecoin|geopolitical|cross_asset|crypto_native|unknown",
  "emergency_level": "watch|high|critical",
  "confirmation_level": "rumor|single_source|multi_source|official|market_dislocation|official_and_market",
  "source_count": 0,
  "official_confirmed": false,
  "market_dislocation": false,
  "btc_microstructure_confirmation": false,
  "cross_asset_confirmation": false,
  "rumor_risk": false,
  "raw_title": "",
  "raw_url": "",
  "source_hash": "",
  "published_at": "",
  "reason_codes": [],
  "source_lineage": [],
  "evidence": {
    "btc_return_5m": null,
    "btc_return_5m_z": null,
    "oi_change_15m_z": null,
    "liquidation_z": null,
    "dxy_move_z": null,
    "us2y_move_z": null,
    "ndx_move_z": null
  },
  "data_quality_flags": []
}
```

## 数据源

### A. Official Shock Sources

优先接入：

```text
Federal Reserve RSS / press releases / speeches & testimony
SEC RSS / press releases
U.S. Treasury press releases
```

可配置接入：

```text
White House statements
Binance / Coinbase / major exchange official announcements or status pages
Major stablecoin issuer official announcements
```

规则：

```text
official hit 必须有 raw_url、source_hash、published_at。
official source 失败必须写 source_fetch lineage。
official source 不可用时不能伪装为 official live。
```

### B. Market Shock Sources

短期先使用现有可得数据：

```text
BTC 5m return
BTC 5m realized-vol adjusted z-score
BTC 15m realized-vol adjusted z-score
```

后续扩展：

```text
OI 15m change z
liquidation spike z
funding / basis abnormal move
DXY / US 2Y / NDX synchronized shock
```

规则：

```text
BTC 5m move > 2σ => high candidate
BTC 5m move > 3σ + OI/liquidation/cross-asset confirmation => critical
BTC fixed 3% / 6% threshold can remain as fallback only
```

### C. Trusted Non-Official Sources

可选，不作为本任务首要交付：

```text
trusted news feeds
prediction-market sudden repricing
secondary macro calendar source emergency notice
```

规则：

```text
single trusted source => max watch/high depending on market reaction
rumor => max watch
multi-source + market reaction => high
official confirmation or market-confirmed extreme dislocation => critical
```

## 分类规则

### critical

```text
official policy/regulatory/exchange/stablecoin hit
or BTC 5m return z >= 3 with OI/liquidation/cross-asset confirmation
or cross-asset shock propagates to BTC with BTC microstructure confirmation
```

输出：

```text
event_window_state = unscheduled_shock_confirmed
emergency_level = critical
trade_permission_modifier = event_lock
ordinary_radar_trust = blocked
```

### high

```text
BTC 5m return z >= 2
or official source hit with non-critical policy relevance
or multi-source trusted hit
or prediction-market / cross-asset repricing with visible BTC reaction
```

输出：

```text
event_window_state = unscheduled_shock_watch
emergency_level = high
trade_permission_modifier = watch_only
ordinary_radar_trust = low
```

### watch

```text
single trusted source
or rumor with visible market reaction
or weak market dislocation without confirmation
```

输出：

```text
event_window_state = unscheduled_shock_watch
emergency_level = watch
trade_permission_modifier = reduce_size
ordinary_radar_trust = reduced
```

## 实现范围

### 1. Connector

新增或扩展：

```text
backend/src/onlybtc/event_window/connectors/shock_lane.py
```

职责：

```text
collect_official_shocks(now)
collect_market_shocks(now)
collect_shock_fast_lane(now)
normalize_shock_item(raw)
classify_shock(item)
```

### 2. Watchtower

扩展：

```text
build_event_window_payload(... shocks=...)
_state_from_inputs(...)
_shock_fast_lane(...)
```

要求：

```text
critical shock 覆盖 scheduled calendar。
high shock 不覆盖成 critical，但必须进入 high alert。
watch shock 只降低 ordinary radar trust，不触发 event_lock。
```

### 3. SQLite / Replay

要求：

```text
shock item 写入 event_watchtower timeline / snapshot payload。
source_fetch lineage 写入 source_fetches。
history replay 能看到 shock item 和当时 overlay。
```

### 4. API

复用并补齐：

```text
GET /api/event-window/shock-lane/latest
GET /api/event-window/shock-lane/history
GET /api/event-window/alerts
```

要求：

```text
无 shock 时返回结构化空态，不 500。
high / critical shock 进入 alerts。
```

### 5. 前端

要求：

```text
全局浮窗能消费 high / critical shock。
事件子页面 Shock Lane 区块显示 source_count、confirmation_level、market_dislocation、source_lineage。
Dashboard summary widget 后续 P5-C66 消费 high / critical 状态。
```

## DoD

- [ ] `shock_fast_lane_items` 可由真实 official / market input 写入。
- [ ] official shock item 必须带 `raw_url`、`source_hash`、`published_at`、`source_lineage`。
- [ ] market shock item 必须带 `btc_return_5m` 或 `btc_return_5m_z`。
- [ ] 单一 rumor 不允许触发 critical。
- [ ] high shock 可以触发 `watch_only` / `ordinary_radar_trust=low`。
- [ ] critical shock 可以触发 `event_lock` / `ordinary_radar_trust=blocked`。
- [ ] `unscheduled_shock_confirmed` 优先级高于 scheduled `event_lock`。
- [ ] high / critical shock 写入 SQLite snapshot / timeline / alerts。
- [ ] `/api/event-window/shock-lane/latest` 和 history 能返回结构化 shock 数据。
- [ ] 前端浮窗或事件子页面能看到 high / critical shock。
- [ ] 单元测试覆盖 official shock、market shock、rumor downgrade、scheduled state override。
- [ ] Event Window HTML 1 / HTML 2 重新生成后能审计 shock lane。

## 验收命令

```powershell
$env:PYTHONPATH='backend/src'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_event_watchtower.py -q
.\.venv\Scripts\python.exe scripts\generate_event_window_source_audit_html.py
.\.venv\Scripts\python.exe scripts\generate_event_window_state_overlay_llm_audit_html.py
```

如涉及前端：

```powershell
cd frontend
npm run build
```

## 依赖

- P1-C57
- P1-C59
- P3-C56
- P8-C35
- P8-C36
- P9-C40
- P9-C42
- P5-C64
- P5-C65

## 下一步

完成后进入：

```text
P5-C66 Dashboard 事件窗口 Summary Widget 改造
```
