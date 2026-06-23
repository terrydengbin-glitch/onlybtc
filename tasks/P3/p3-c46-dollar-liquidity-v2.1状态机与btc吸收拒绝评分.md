# P3-C46 / Dollar Liquidity v2.1 状态机与 BTC 吸收/拒绝评分

## 状态

DONE

## 背景

`dollar_liquidity` 需要升级为 BTC 趋势确认/反证模块。核心不再是美元流动性 level，而是：

```text
liquidity impulse + repo funding pressure + BTC response
```

## 目标

新增 `p3.c46.dollar_liquidity.v2.1` profile，输出结构化状态与分数。

## 输出契约

```json
{
  "module": "dollar_liquidity",
  "version": "p3.c46.dollar_liquidity.v2.1",
  "module_purpose": "confirm_or_refute_btc_trend_by_usd_liquidity_and_funding_conditions",
  "data_freshness": {},
  "liquidity_level": {},
  "liquidity_impulse": {},
  "reserve_buffer": {},
  "liquidity_drain_pressure": {},
  "repo_funding_pressure": {},
  "btc_response_confirmation": {},
  "dollar_liquidity_state": "liquidity_tailwind_confirmed|liquidity_tailwind_rejected|liquidity_headwind_confirmed|btc_internal_strength_against_liquidity_headwind|funding_stress_override|liquidity_neutral",
  "module_direction": "bullish|bearish|neutral",
  "module_score": 0,
  "risk_score": 0,
  "confidence_adjustment": 0,
  "support_drivers": [],
  "pressure_drivers": [],
  "risk_drivers": [],
  "context_notes": []
}
```

## 状态机

```text
liquidity_tailwind_confirmed:
  liquidity_impulse_score > 0
  funding_pressure_score >= 0
  btc_response_score > 0

liquidity_tailwind_rejected:
  liquidity_impulse_score > 0
  btc_response_score < 0

liquidity_headwind_confirmed:
  liquidity_impulse_score < 0
  funding_pressure_score <= 0
  btc_response_score < 0

btc_internal_strength_against_liquidity_headwind:
  liquidity_impulse_score < 0
  btc_response_score > 0

funding_stress_override:
  funding_pressure_score <= -0.25
  or repo_stress_flag = true
```

## 评分建议

```text
module_score =
  0.30 * liquidity_impulse_score
+ 0.20 * reserve_buffer_score
+ 0.15 * tga_drain_score
+ 0.20 * funding_pressure_score
+ 0.30 * btc_response_confirmation_score

module_score = clamp(module_score, -0.45, +0.45)
```

## DoD

- `dollar_liquidity` 不再由单项原始指标直接决定方向。
- 能区分：
  - 流动性顺风且 BTC 吸收。
  - 流动性顺风但 BTC 拒绝。
  - 流动性逆风且 BTC 跟跌。
  - 流动性逆风但 BTC 抗跌。
  - repo funding stress override。
- `rrp_depleted=true` 时，ON RRP 下降不允许贡献强 bullish 分。
- `repo_funding_pressure` 使用 SOFR-IORB spread / stress z，而不是 SOFR 绝对值。
- P3 测试覆盖以上状态矩阵。

## 验证建议

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
```

## Execution Record

- DONE: added `p3.c46.dollar_liquidity.v2.1` semantic profile.
- DONE: implemented liquidity tailwind/headwind, BTC absorbing/rejecting/resisting and funding stress override states.
- Verified: target regression suite -> 124 passed.
