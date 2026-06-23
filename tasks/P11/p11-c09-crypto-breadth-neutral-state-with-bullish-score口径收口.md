# P11-C09 / Crypto Breadth neutral state with bullish score 口径收口

## 状态

DONE

## Execution Record

### 2026-06-23 / Done

- 修复 `crypto_breadth.v3` fallback 口径：`neutral_wait_confirm` 不再携带明显 bullish 的 `module_direction/module_score`。
- 新增常量：
  - `CRYPTO_BREADTH_NEUTRAL_DEADBAND = 0.08`
  - `CRYPTO_BREADTH_MILD_BULLISH_THRESHOLD = 0.12`
- 行为收口：
  - fallback raw score 低于 mild bullish threshold 时，`neutral_wait_confirm` 会将 `module_direction` 收口为 `neutral`，并将 `module_score` 限制在 neutral deadband 内。
  - fallback raw score 达到 mild bullish threshold 时，不再保留 `neutral_wait_confirm`，会升级为可解释的专项状态，例如 `alt_beta_rotation` / `btc_broad_confirmed_uptrend` / `btc_defensive_leadership` / `risk_off_but_breadth_improving`。
- 新增 P3 测试覆盖：
  - weak BTC / improving breadth 但未达升级阈值时，不产生 bullish neutral mismatch。
  - improving breadth + positive fallback score 时，升级为 `alt_beta_rotation` 且方向为 `bullish`。
- P4.5 / API / UI 链路确认：`p45_dashboard` 已优先投影 `crypto_breadth_state -> display_state`，前端已有 `crypto_breadth_state` 优先展示口径，本次无需改 Vue。

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
40 passed

.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
26 passed

.\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\algorithms\p3.py backend\src\onlybtc\api\p45_dashboard.py
passed

npm run build
passed
```

### 2026-06-23 / Start

- 用户明确开始任务，按当前优先级执行 P11-C09。
- 本卡聚焦 `crypto_breadth.v3` 状态、方向、分数展示口径一致性。
- 约束：不改 P1 采集源，不改其他 radar module 聚合权重；优先修 P3 状态机/评分映射与测试覆盖。

## 背景

Run once 审计发现 `crypto_breadth` 出现状态标签与方向分数不完全一致：

```text
crypto_breadth_state = neutral_wait_confirm
module_direction = bullish
module_score = +0.1889 ~ +0.1953
```

这不是链路阻塞问题，但容易造成前端和研究报告语义误读：用户看到 `neutral_wait_confirm` 会理解为中性等待确认，但聚合层实际仍吃到接近 mild bullish 的正分。

## 目标

收口 `crypto_breadth.v3` 的状态机、方向、分数和展示口径，让专项状态优先且语义一致。

核心原则：

```text
如果状态是 neutral_wait_confirm：
  module_direction 不应是明显 bullish
  module_score 应落在 neutral deadband 内

如果 module_score 已达到 mild bullish：
  crypto_breadth_state 应升级到能解释正分的状态
```

## 范围

- P3 `crypto_breadth.v3` 状态机与评分映射。
- P4.5 / P9 / P5 对 `crypto_breadth_state`、`module_direction`、`module_score` 的展示口径。
- 不修改 P1 采集源。
- 不改变其他 radar module 的聚合权重。

## 建议处理方向

1. 增加 neutral state clamp：

```text
neutral_wait_confirm:
  module_direction = neutral
  module_score range = -0.08 ~ +0.08
```

2. 如果连续评分强于 neutral deadband，则状态必须升级：

```text
module_score >= +0.12:
  不允许保持 neutral_wait_confirm
  根据分层 basis 选择：
    risk_off_but_breadth_improving
    alt_beta_rotation
    btc_defensive_leadership
    btc_broad_confirmed_uptrend
```

3. 前端展示优先级保持：

```text
crypto_breadth_state > display_state > module_direction/trend fallback
```

## DoD

- `crypto_breadth_state=neutral_wait_confirm` 时，`module_direction=neutral`。
- `neutral_wait_confirm` 时，`module_score` 不超过 neutral deadband。
- `module_score >= +0.12` 时，不允许输出 `neutral_wait_confirm`。
- P3 测试覆盖：
  - weak/up BTC anchor + weak breadth + healthy quality，不应产生 bullish neutral mismatch。
  - improving breadth + positive score，应输出可解释正分的状态。
- P4.5 / API / UI 展示不再出现“状态中性但标签/分数偏多”的冲突。

## 验证建议

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py backend\tests\test_p45_dashboard_api.py -q
npm run build
```
