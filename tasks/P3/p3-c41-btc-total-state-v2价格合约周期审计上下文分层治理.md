# P3-C41 / BTC Total State v2：价格、合约、周期、审计上下文分层治理

## 状态
DONE

## 背景

`btc_total_state` 当前仍容易被理解为“所有 BTC 相关指标加权求方向”的模块。它同时包含：

```text
btc_price
btc_1h_close
btc_funding_rate
btc_open_interest
btc_halving_estimated_days
btc_block_height
btc_halving_blocks_remaining
```

这些指标的业务属性不同：价格和合约可参与短线状态判断，减半与区块高度只应作为周期背景或审计上下文。将它们混在同一个方向层里，容易让 P4.5 / UI 误读为“减半天数、区块高度也影响 24h 方向”。

专业口径上，Open Interest 表示市场参与者持有的未平仓合约数量，适合判断趋势背后的参与度和强度，但不能脱离价格方向单独给多空结论；Funding Rate 是永续合约锚定现货价格的多空资金费率机制，更多反映拥挤和持仓成本，而不是纯趋势方向；Bitcoin halving 是每 210,000 blocks 一次的发行周期变化，属于长周期供给背景。

## 核心目标

将 `btc_total_state` 升级为：

```text
btc_total_state
= btc_short_term_direction
+ perp_confirmation
+ cycle_context
+ audit_context
```

真正影响 24h / 短线方向的只允许：

```text
price_state
perp_state
```

只解释背景或审计的范围：

```text
cycle_context
audit_context
```

一句话边界：

```text
btc_total_state 只回答：BTC 当前短线内生状态是什么？
```

它不再负责把减半、区块高度、Funding、OI、价格全部揉成一个方向分。

## 与 derivatives_crowding 的边界

两个模块允许共享 `btc_funding_rate` 和 `btc_open_interest`，但解释权不同：

```text
btc_total_state:
  BTC 自身短线状态体温计。
  funding / OI 只是价格状态的合约确认层。

derivatives_crowding:
  合约杠杆压力表。
  funding / OI / long-short ratios 用于判断拥挤、过热、挤压、清算风险。
```

示例：

```text
price up + OI up + funding mild

btc_total_state:
  price_up_confirmed

derivatives_crowding:
  not_crowded / healthy_participation
```

```text
price up + OI up + funding extreme

btc_total_state:
  overheated_upside，方向仍偏多但追分受限

derivatives_crowding:
  long_crowding / liquidation risk elevated
```

## 指标分层

第一阶段复用现有数据，不新增 P1 数据源。

```text
price_state:
  raw:
    btc_price
    btc_1h_close
  preferred existing derived/context:
    btc_return_1h
    btc_return_4h
    btc_return_24h
    btc_price.change_24h
    btc_1h_close.change_24h

perp_state:
  raw:
    btc_funding_rate
    btc_open_interest
  first-stage derived/context:
    btc_open_interest.change_24h
    btc_funding_rate band

cycle_context:
  btc_halving_estimated_days
  btc_halving_blocks_remaining

audit_context:
  btc_block_height
```

后续可另开 P1/P2 卡补充：

```text
btc_1h_return_pct
btc_4h_return_pct
btc_24h_return_pct
btc_oi_change_1h_pct
btc_oi_change_4h_pct
btc_oi_change_24h_pct
btc_oi_zscore
btc_funding_band
```

本卡第一阶段不把范围扩大成数据源扩建工程。

## P2 / Registry 调整建议

新增或调整 metric role：

```text
price_state
perp_state
cycle_context
audit_context
```

目标规则：

```text
btc_price:
  role = price_state
  composite-only / not standalone driver

btc_1h_close:
  role = price_state
  composite-only / not standalone driver

btc_funding_rate:
  role = perp_state
  composite-only
  不单独进入 support_drivers / pressure_drivers

btc_open_interest:
  role = perp_state
  composite-only
  不单独进入 support_drivers / pressure_drivers

btc_halving_estimated_days:
  role = cycle_context
  weight = 0
  affects_signal = false
  affects_confidence = false

btc_halving_blocks_remaining:
  role = cycle_context
  weight = 0
  affects_signal = false
  affects_confidence = false

btc_block_height:
  role = audit_context
  weight = 0
  affects_signal = false
  affects_confidence = false
```

如果本卡新增 `driver_eligible` 字段，则上述 context/composite 指标应设置：

```text
driver_eligible = false
```

若为控制改动面暂不新增字段，则使用 `role + affects_signal=false + score_bucket_v2=context_only` 达到等效过滤。

## P3 Profile v2 输出契约

新增默认 profile：

```text
p3.c41.btc_total_state.v2
```

输出结构：

```json
{
  "direction_driver_scope": ["price_state", "perp_state"],
  "context_only_scope": ["cycle_context", "audit_context"],

  "price_state": {
    "state": "price_up|price_down|price_flat|price_context_missing",
    "strength": "weak|normal|strong",
    "basis": {},
    "affects_direction": true
  },

  "perp_state": {
    "state": "healthy_participation|long_crowding|short_crowding|short_covering|deleveraging|perp_neutral",
    "confirmation": "confirming|weak_confirming|not_confirming|risk_only",
    "risk_state": "normal|elevated|extreme",
    "basis": {},
    "affects_direction": true
  },

  "cycle_context": {
    "state": "halving_context_only",
    "basis": {},
    "affects_direction": false,
    "affects_confidence": false
  },

  "audit_context": {
    "state": "block_height_synced|block_height_stale|block_height_missing",
    "basis": {},
    "affects_direction": false,
    "affects_confidence": false
  },

  "btc_short_term_state": "neutral_wait_confirm",
  "context_notes": [],
  "audit_notes": []
}
```

## 组合规则

组合规则写入 P3 专属 profile，不继续依赖通用 metric rule 直接解释。

```text
price up + OI up + funding mild
-> btc_short_term_state = price_up_confirmed
-> module_direction = bullish
-> module_score ~= +0.35
-> perp_state = healthy_participation
-> risk_state = normal
```

```text
price up + OI down
-> btc_short_term_state = short_covering_bounce
-> module_direction = bullish
-> module_score ~= +0.18
-> perp_confirmation = weak_confirming
-> risk_state = normal
```

```text
price up + OI up + funding elevated/extreme
-> btc_short_term_state = overheated_upside
-> module_direction = bullish
-> module_score ~= +0.20
-> perp_state = long_crowding
-> risk_state = elevated|extreme
```

注意：

```text
overheated_upside 不是 bearish。
它表示方向仍偏多，但不适合继续强化 bullish score，应提高 risk_score。
```

```text
price down + OI up + funding positive
-> btc_short_term_state = long_crowding_downside
-> module_direction = bearish
-> module_score ~= -0.42
-> perp_state = long_crowding
-> risk_state = elevated
```

```text
price down + OI down
-> btc_short_term_state = deleveraging_downside
-> module_direction = bearish
-> module_score ~= -0.25
-> perp_state = deleveraging
-> risk_state = normal
```

```text
price flat + funding mild + OI flat
-> btc_short_term_state = neutral_wait_confirm
-> module_direction = neutral
-> module_score = 0
-> perp_state = perp_neutral
-> risk_state = normal
```

```text
funding negative + price stable/up
-> btc_short_term_state = short_squeeze_potential
-> module_direction = neutral|bullish
-> perp_state = short_crowding
-> perp_confirmation = risk_only
```

关键禁止项：

```text
funding positive 不能直接等于 bullish。
OI 高不能直接等于 bullish / bearish。
halving / block height 不能影响 24h direction。
```

## P4.5 / P9 / P5 展示要求

P4.5 报告与 API 需要区分：

```text
direction drivers
risk drivers
context notes
audit notes
```

不得把以下内容写成短线方向依据：

```text
减半天数影响短线方向
区块高度影响 BTC 24h 判断
funding positive 所以 bullish
OI 高所以 bullish / bearish
```

P5 Radar Detail 后续应展示四块：

```text
短线方向
合约确认
周期背景
数据审计
```

本卡至少保证字段可透传、可消费；UI 精修可后续单独开 P5 卡。

## DoD

1. `btc_total_state` 输出：

```text
price_state
perp_state
cycle_context
audit_context
btc_short_term_state
context_notes
audit_notes
```

2. `halving` 与 `block height`：

```text
metric_score = 0
metric_effective_score = 0
affects_signal = false
affects_confidence = false
score_bucket_v2 = context_only 或 audit_only
不进入 support_drivers
不进入 pressure_drivers
```

3. `funding / OI` 不允许单独生成 bullish / bearish 结论，必须结合 `price_state`。

4. P3 测试覆盖：

```text
price up + OI up + funding mild
price up + OI down
price up + OI up + funding extreme
price down + OI up + funding positive
price down + OI down
price flat + OI flat + funding mild
funding negative + price stable/up
```

5. P4.5 报告不再出现以下误导：

```text
减半天数影响短线方向
区块高度影响 BTC 24h 判断
funding positive 所以 bullish
OI 高所以 bullish / bearish
```

6. API 透传 v2 字段，UI 可消费。

7. 旧版 `p3.c27.btc_total_state.v1` 可保留兼容，但默认输出 `p3.c41.btc_total_state.v2`。

## 不做范围

- 不新增 P1 数据源。
- 不强制本卡完成 P5 四区块最终视觉改造。
- 不改变 `derivatives_crowding` 的完整拥挤度职责。
- 不删除 `btc_total_state` 与 `derivatives_crowding` 对 `funding / OI` 的共享数据，只治理解释边界。

## 执行记录

- `backend/src/onlybtc/algorithms/p3.py` 新增 `p3.c41.btc_total_state.v2` profile。
- `btc_total_state` 输出 `price_state / perp_state / cycle_context / audit_context / btc_short_term_state / context_notes / audit_notes`。
- `halving / block height` 保持 `metric_score = 0`、`metric_effective_score = 0`、`driver_eligible = false`，只作为 context/audit。
- `funding / OI` 只在 `price_state` 组合规则中确认，不单独生成 bullish/bearish 结论。
- 新增 P3 组合矩阵测试，覆盖上涨确认、空头回补、上涨过热、下跌多头拥挤、去杠杆下跌、横盘确认、潜在逼空。

## 测试记录

```text
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py::test_btc_total_state_v2_combines_price_oi_and_funding_states -q
1 passed

.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
29 passed
```

## 上下游任务

```text
P1-C43  派生价格与 OI 变化指标准备
P2-C26  指标角色、权重与 composite-only 契约
P3-C41  BTC Total State v2 profile 主体
P4.5-C26 研报方向/风险/上下文/审计分层解释
P8-C18  SQLite payload 持久化与回放兼容
P9-C24  API 透传与契约
P5-C43  前端四区块展示与方向防误导
P11-C03 Metric node value 与 score 并列展示
```
