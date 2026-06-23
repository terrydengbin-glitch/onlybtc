# P3-C28 P1 Radar 高零分模块语义补全

## 状态

DONE

## Phase

P3 算法、事件窗口与评分层

## 背景

P3-C27 处理 P0 核心模块后，还需要补齐若干高 zero / 高解释价值模块的语义规则。本卡仍限定在现有 14 个 Radar 内，不新增情绪雷达、事件雷达或策略雷达。

P1 模块：

```text
options_volatility
asia_risk
crypto_breadth
trade_structure_flow
btc_adoption
```

## 目标

- `options_volatility` 区分正常中性、保护需求、gamma pinning 和 expiry magnet。
- `asia_risk` 用组合 risk-off，而不是单指标 neutral。
- `crypto_breadth` 输出 BTC 独强 / 风险扩散 / 情绪修复 / 过热失败等 regime。
- `trade_structure_flow` 拆分 aggressive flow、liquidation flow、mempool pressure、stablecoin buying power。
- `btc_adoption` 降低短线权重，作为结构健康上下文。

## 模块规则

### options_volatility

```text
options_iv normal -> neutral_confirmed
options_rv normal -> neutral_confirmed
basis flat -> neutral_confirmed
put_call_ratio elevated -> downside hedge demand
skew extreme -> directional/risk signal
gamma wall close -> pinning / volatility risk
max pain close -> expiry magnet
```

### asia_risk

组合判断：

```text
USDCNH up + USDJPY up + Hang Seng Tech down -> Asia risk pressure
JGB 10Y up + Nikkei down -> Japan rates risk
USDCNH down + HST/Nikkei up -> Asia risk support
```

`hibor` provider_required 继续作为 data_boundary，不计 decision zero。

### crypto_breadth

```text
BTC.D up + ETHBTC down -> BTC solo strength, not broad risk-on
BTC.D down + ETHBTC up + Top50 breadth up -> risk diffusion
Fear & Greed low but improving -> sentiment repair
Fear & Greed high + breadth weak -> overheating / failed diffusion
TOTAL2 down + Top50 strength up -> partial rebound, not broad bull
```

### trade_structure_flow

```text
taker_buy_sell_ratio > 1 -> aggressive buy
taker_buy_sell_ratio < 1 -> aggressive sell
short liquidation high + price up -> short squeeze, chase risk
long liquidation high + price down -> long flush, possible cleanup
stablecoin buying power up -> latent bid support
stablecoin buying power down -> weak marginal buying power
mempool extreme only -> pressure/risk, otherwise context
```

### btc_adoption

```text
24h horizon weight: 0.2
3d horizon weight: 0.5
7d / structural weight: 1.0
Lightning / nodes / Tor normal -> network_health_context
```

## DoD

- 五个 P1 模块均有明确 zero v2 分类。
- 正常波动 / 正常结构不再计为 rule gap。
- `crypto_breadth` 能解释 BTC 独强与全市场风险扩散的区别。
- `trade_structure_flow` 不再简单加总清算、mempool、stablecoin buying power。
- `btc_adoption` 不再拖短线方向，但保留结构解释。
- P3 HTML / P4.5 HTML / P5 Evidence 能展示新增语义字段。
- P1/P2/P3/P4.5 全链条重跑通过。

## 关联任务

P3-C26, P3-C27, P4.5-C20, P5-C10, P5-C17

## Execution Notes

- Added P1 module semantic profiles for `options_volatility`, `asia_risk`, `crypto_breadth`, `trade_structure_flow`, and `btc_adoption`.
- Options now exposes volatility pressure, hedge demand, gamma/pinning risk, and volatility state.
- Asia risk now exposes composite risk-off/mixed state.
- Crypto breadth now exposes risk-expansion / breadth-pressure / BTC-specific regime.
- Trade structure now separates aggressive flow, liquidation flow, stablecoin buying power, and mempool context.
- BTC adoption now marks structural horizon focus and short-term direction weight.
- Validation: `python -m pytest backend/tests/test_p3_pipeline.py -q` passed, 16 tests.
- Full chain validation: latest P4.5 run `p45final-20260523080308-73db05` passed contract validation; P3 bucket v2 distribution was `positive=22`, `negative=28`, `neutral_confirmed=45`, `context_only=14`, `combo_required=2`, `rule_gap_zero=0`, `unavailable=7`.
