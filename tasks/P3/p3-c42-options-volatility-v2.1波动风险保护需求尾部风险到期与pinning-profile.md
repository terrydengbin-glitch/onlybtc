# P3-C42 / Options Volatility v2.1：波动风险、保护需求、尾部风险、到期与 pinning profile

## 状态

DONE

## 背景

`options_volatility` 的正确问题不是“BTC 要涨还是要跌”，而是：

```text
是否进入波动扩张？
是否有下方保护需求？
是否存在尾部风险定价？
是否临近大额到期压力？
是否靠近 max pain / gamma wall，导致突破信心下降？
```

## 模块定位

```text
primary_purpose = volatility_risk_and_expiry_structure
secondary_purpose = confidence_adjustment
forbidden_purpose = directional_alpha
```

## 输出契约

新增默认 profile：

```text
p3.c42.options_volatility.v2.1
```

必须输出：

```json
{
  "module": "options_volatility",
  "version": "p3.c42.options_volatility.v2.1",
  "module_purpose": "volatility_risk_and_expiry_structure",
  "module_direction": "neutral",
  "module_score": 0,
  "module_effective_score": 0,
  "risk_score": 0,
  "confidence_adjustment": 0,
  "trade_permission_hint": "normal|reduce_breakout_confidence|increase_risk_mode|avoid_chasing|wait_post_expiry",
  "volatility_regime": {},
  "protection_demand": {},
  "tail_risk": {},
  "expiry_pressure": {},
  "pinning_structure": {},
  "data_quality": {},
  "options_short_term_state": "vol_neutral",
  "risk_drivers": [],
  "context_notes": [],
  "summary": ""
}
```

## 状态优先级

```text
1. tail_risk_elevated
2. downside_protection_bid
3. vol_expansion_risk
4. large_expiry_near
5. pinning_likely
6. vol_compression
7. vol_neutral
```

特殊冲突规则：

```text
pinning_likely + vol_expansion_risk + expiry_days <= 2:
  options_short_term_state = pinning_before_expiry_vol_after

pinning_likely + vol_expansion_risk + expiry_days > 2:
  options_short_term_state = vol_expansion_risk_with_structure_resistance
```

## 风险评分

```text
module_direction = neutral
module_score = 0
module_effective_score = 0
```

风险分单独计算：

```text
risk_score = max(sub_risk_scores) * 0.60 + weighted_avg(sub_risk_scores) * 0.40
```

## DoD

- P3 profile 输出 5 个结构层：volatility_regime、protection_demand、tail_risk、expiry_pressure、pinning_structure。
- `options_volatility` 不进入 directional_score，不改变 final_direction。
- `put_call_ratio`、`options_skew`、`max_pain_distance`、`gamma_wall_proxy_distance` 不允许单独生成 bullish / bearish。
- 数据缺失超过 50% 时输出 `data_quality_degraded`，不输出强状态。
- 测试覆盖 8 个核心场景。

## 测试矩阵

```text
case_01: IV 高于 RV，IV 上升，RV 上升 => vol_expansion_risk
case_02: IV/RV 低，max_pain near，gamma_wall near => pinning_likely
case_03: put_call_ratio 高，downside skew 高 => downside_protection_bid
case_04: expiry_days <= 2，expiry_notional_z 高，max_pain near => pinning_before_expiry_vol_after
case_05: gamma_wall far，IV 上升，RV 上升 => vol_expansion_risk
case_06: skew_abs 高，skew_side unknown，IV 上升 => tail_risk_elevated
case_07: 数据缺失超过 50% => data_quality_degraded，risk_score 降权
case_08: 所有 options 指标正常 => vol_neutral，module_score = 0
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
```
