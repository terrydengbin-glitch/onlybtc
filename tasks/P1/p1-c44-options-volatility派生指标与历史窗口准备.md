# P1-C44 / Options Volatility 派生指标与历史窗口准备

## 状态

DONE

## 背景

`options_volatility` v2.1 需要判断波动扩张、保护需求、尾部风险、到期压力与 pinning 结构。原始指标包括：

```text
options_iv
options_rv
put_call_ratio
options_skew
options_expiry_notional
max_pain_distance
gamma_wall_proxy_distance
```

这些原始值不能直接解释为 bullish / bearish。P1 需要先准备稳定的派生输入和历史窗口，供 P2/P3 做组合判断。

## 目标

为 `options_volatility` 准备以下派生指标或可计算上下文：

```text
iv_rv_spread
iv_rv_ratio
iv_change_1d
iv_change_3d
rv_change_1d
rv_change_3d
put_call_ratio_z
put_call_ratio_change_1d
skew_abs
skew_side
expiry_days
expiry_notional_z
expiry_notional_pct_oi
max_pain_distance_pct
gamma_wall_distance_pct
gamma_wall_side
```

## 范围

- 复用现有期权数据源，不在本卡新增付费源。
- 缺少到期日、gamma wall price、max pain price 等上游字段时，允许输出 `unknown` / `missing`，不得伪造强状态。
- 历史窗口优先使用生产同 run / 同 run_mode 数据，避免 mock 或旧环境污染。
- 派生指标必须保留 raw basis，方便 P3/P4.5/UI 回查。

## DoD

- P1 输出或可供 P3 计算上述派生指标。
- 缺失数据有显式 `missing` / `unknown` 标记。
- 数据缺失超过 50% 时，后续 P3 可识别 `data_quality_degraded`。
- 不在 P1 产生 bullish / bearish 方向结论。
- P1/P8 相关测试通过。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```
