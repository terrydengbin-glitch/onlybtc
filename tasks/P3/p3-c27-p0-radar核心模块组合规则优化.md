# P3-C27 P0 Radar 核心模块组合规则优化

## 状态

DONE

## Phase

P3 算法、事件窗口与评分层

## 背景

P3-C26 会解决 zero 语义，但部分核心模块仍需要组合规则才能避免误读。优先优化现有 14 个 Radar 中影响最大的 P0 模块，不新增 Radar。

P0 模块：

```text
event_policy
onchain_valuation
fund_flow
derivatives_crowding
btc_total_state
```

## 目标

- `event_policy` 从方向模块升级为风险窗口 / lock 模块。
- `onchain_valuation` 使用 BTC price 与成本基础组合。
- `fund_flow` 显式表达绝对资金方向、边际改善和冲突。
- `derivatives_crowding` 使用 price + OI + funding 组合。
- `btc_total_state` 拆分 price_state / perp_state / cycle_context / audit_context。

## 模块规则

### event_policy

倒计时类指标不再硬给 bullish/bearish：

```text
0-24h: event_risk_score 70-90
1-3d: event_risk_score 40-70
3-7d: event_risk_score 20-40
>7d: event_risk_score 0-20
```

输出：

```json
{
  "event_risk_score": 72,
  "event_uncertainty_score": 80,
  "event_lock_level": "soft",
  "main_event": "PCE / FOMC / CPI / Fed speech"
}
```

### onchain_valuation

成本基础必须结合 BTC 价格：

```text
BTC > STH cost basis + 3% -> bullish
BTC near STH ±2% -> neutral_confirmed / key test
BTC < STH - 2% -> bearish
BTC > realized price and MVRV low -> structural healthy
BTC below realized price -> structural risk
```

### fund_flow

ETF 绝对方向和边际变化分开：

```json
{
  "fund_flow_absolute_direction": "bearish",
  "fund_flow_marginal_direction": "improving",
  "fund_flow_conflict_level": "high"
}
```

规则：

```text
ETF net flow < 0 -> absolute bearish
ETF outflow narrowing -> pressure_easing, not bullish
exchange balance falling -> sell supply easing / bullish support
ETF negative + exchange balance positive -> bearish_but_improving or conflict
```

### derivatives_crowding

组合 price / OI / funding：

```text
price up + OI up + funding mild -> trend confirmation
price up + OI down -> short-cover, lower durability
price down + OI up + funding positive -> long crowding downside risk
price down + OI down -> deleveraging
funding high + OI high -> crowded risk
```

### btc_total_state

拆成内部语义：

```text
price_state: btc_price / btc_1h_close
perp_state: funding / OI, with duplicate adjustment
cycle_context: halving days / blocks
audit_context: block height
```

## DoD

- 五个 P0 模块均有组合规则测试。
- `event_policy` 倒计时类进入 risk/context，不计 decision zero。
- `onchain_valuation` 成本基础类不再长期 combo_required，能根据 BTC price 触发方向或 key test。
- `fund_flow` 能输出 `bearish_but_improving` / conflict，并解释 ETF 与 exchange balance 的冲突。
- `derivatives_crowding` 不再只靠 funding 单独给方向。
- `btc_total_state` 不再把减半/区块高度算入短线方向 zero。
- P3 HTML 和 P4.5 Evidence Pack 显示新增字段。
- P1/P2/P3/P4.5 全链条重跑通过。

## 关联任务

P3-C22, P3-C23, P3-C24, P3-C26, P4.5-C20, P5-C03, P5-C17

## Execution Notes

- Added P0 module semantic profiles for `event_policy`, `fund_flow`, `derivatives_crowding`, `onchain_valuation`, and `btc_total_state`.
- Event policy now exposes event risk, uncertainty, lock level, and direction component.
- Fund flow now exposes absolute ETF direction, marginal exchange-balance direction, conflict level, and flow state.
- Derivatives now exposes OI/funding combo state and crowding/liquidation risk.
- On-chain valuation now exposes cost-basis combo state.
- BTC total state now exposes price/perp/cycle/audit groups.
- Validation: `python -m pytest backend/tests/test_p3_pipeline.py -q` passed, 15 tests.
