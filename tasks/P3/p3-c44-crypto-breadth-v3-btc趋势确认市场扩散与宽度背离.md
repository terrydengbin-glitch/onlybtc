# P3-C44 / Crypto Breadth v3：BTC 趋势确认、市场扩散与宽度背离

## 状态

DONE

## 目标

新增 `p3.c44.crypto_breadth.v3` profile，将 `crypto_breadth` 升级为 BTC trend confirmation by crypto market diffusion 模块。

## 输出契约

```json
{
  "module": "crypto_breadth",
  "version": "p3.c44.crypto_breadth.v3",
  "module_purpose": "btc_trend_confirmation_by_crypto_market_diffusion",
  "primary_question": "is_btc_trend_confirmed_or_refuted_by_crypto_market_breadth",
  "btc_trend_anchor": {},
  "breadth_participation": {},
  "market_cap_diffusion": {},
  "btc_vs_alt_leadership": {},
  "sector_risk_appetite": {},
  "breadth_quality": {},
  "crypto_breadth_state": "btc_broad_confirmed_uptrend|narrow_btc_rally_fragile|btc_defensive_leadership|alt_beta_rotation|breadth_bearish_divergence|broad_risk_off|risk_off_but_breadth_improving|alt_chase_overheat|neutral_wait_confirm",
  "module_direction": "bullish|bearish|neutral",
  "module_score": 0,
  "confidence_adjustment": 0,
  "risk_score": 0,
  "btc_implication": "trend_confirmed|trend_fragile|defensive_bid|rotation_supportive_but_not_outperformance|risk_off_pressure|early_repair|neutral",
  "support_drivers": [],
  "pressure_drivers": [],
  "risk_drivers": [],
  "context_notes": []
}
```

## 状态机

必须覆盖：

```text
btc_broad_confirmed_uptrend
narrow_btc_rally_fragile
btc_defensive_leadership
alt_beta_rotation
breadth_bearish_divergence
broad_risk_off
risk_off_but_breadth_improving
alt_chase_overheat
neutral_wait_confirm
```

## 评分

```text
raw_score =
  0.25 * btc_anchor_score
+ 0.25 * breadth_participation_score
+ 0.20 * market_cap_diffusion_score
+ 0.15 * leadership_score
+ 0.10 * sector_risk_appetite_score
+ 0.05 * volume_breadth_score
- penalty_score

module_score = clamp(raw_score, -0.40, +0.40)
```

## DoD

- `crypto_breadth` 输出 v3 六层结构。
- `btc_dominance` / `eth_btc` / `sector_heat` 不再单项决定方向。
- BTC 上涨但宽度弱时能输出 `narrow_btc_rally_fragile` 或 `breadth_bearish_divergence`。
- BTC 弱但宽度修复时能输出 `risk_off_but_breadth_improving`。
- 测试覆盖 8 个状态矩阵。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py backend\tests\test_p45_final_writer.py -q
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
```
