# P11-C10 / Macro Radar BTC relative confirmation missing 分类口径修复

## 状态

DONE

## Execution Record

### 2026-06-23 / Done

- 修复 `macro_radar.v3` 中 `btc_relative_confirmation` 的 `missing` 分类口径。
- 行为收口：
  - `btc_beta_residual`、`btc_vs_ndx_relative_return`、`btc_vs_spx_relative_return` 任一 relative basis 存在时，不再默认输出 `missing`。
  - relative basis 偏弱时输出 `btc_lagging_macro` 或 `btc_rejecting_macro_tailwind`。
  - 宏观逆风下 BTC residual / relative basis 为正时输出 `btc_resisting_macro_headwind`。
  - 只有 BTC relative basis、BTC return、权益 return 都无法支持分类时才输出 `missing`，并带 `missing_reason`。
- API / UI：
  - P45 dashboard API 继续透传 `btc_relative_confirmation.state / basis / missing_reason`。
  - Vue3 Macro Radar 的 BTC Relative Confirmation 卡片在 missing 时展示 `missing_reason`。
- 新增测试覆盖：
  - 宏观顺风 + BTC 相对弱 => `btc_lagging_macro`，不再 `missing`。
  - 宏观逆风 + BTC residual 正 => `btc_resisting_macro_headwind`。
  - 缺少 BTC / equity / relative basis => `missing` 且包含 `missing_reason`。
  - P45 dashboard API 透传 `btc_relative_confirmation.missing_reason`。

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py backend\tests\test_p45_dashboard_api.py -q
70 passed

.\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\algorithms\p3.py backend\src\onlybtc\api\p45_dashboard.py
passed

npm run build
passed
```

### 2026-06-23 / Start

- 用户在 P11-C09 完成后要求继续，按优先级启动 P11-C10。
- 本卡聚焦 `macro_radar.v3` 中 `btc_relative_confirmation` 的状态分类与缺失原因可审计性。
- 约束：不修改宏观原始数据源，不改变 `macro_radar` 总 module weight；优先修 P3 分类逻辑与 P4.5/API/UI 透传测试。

## 背景

Run once 审计发现 `macro_radar.btc_relative_confirmation` 已经具备 residual 与相对收益 basis：

```text
btc_beta_residual = -0.007029
btc_vs_ndx_relative_return = -0.00775
btc_vs_spx_relative_return = -0.00582
```

但输出状态仍为：

```text
btc_relative_confirmation.state = missing
```

这不是运行阻塞问题，但会削弱 `macro_radar.v3` 对 BTC 趋势变化的解释能力。当前更像是分类门槛、字段可用性判定或缺失原因输出不完整。

## 目标

修复 `btc_relative_confirmation` 的分类口径：当 BTC 相对宏观 basis 已存在时，不应简单输出 `missing`；应输出明确状态，或给出可审计的缺失原因。

## 范围

- P3 `macro_radar.v3` 中 `btc_relative_confirmation` 分类逻辑。
- P4.5 / API / UI 对 `btc_relative_confirmation.state`、`btc_beta_residual`、basis 和缺失原因的透传。
- 不修改宏观原始数据源。
- 不改变 `macro_radar` 总 module weight。

## 建议处理方向

1. 明确 missing 条件：

```text
missing 仅允许在以下情况出现：
  btc_return_* 缺失
  nasdaq/sp500 return 全部缺失
  beta/residual 无法计算
```

2. 当 basis 可用但 BTC 相对弱时，输出：

```text
btc_lagging_macro
btc_rejecting_macro_tailwind
```

3. 当 basis 可用但宏观逆风下 BTC 抗跌时，输出：

```text
btc_resisting_macro_headwind
```

4. 如果仍判定 missing，必须输出：

```json
{
  "state": "missing",
  "missing_reason": "...",
  "basis": {...}
}
```

## DoD

- `btc_beta_residual`、`btc_vs_ndx_relative_return`、`btc_vs_spx_relative_return` 可用时，不再默认输出 `missing`。
- 当前审计样例应能归类为 `btc_lagging_macro` 或输出明确 `missing_reason`。
- `macro_radar.summary` 不再出现 “BTC relative=missing” 但同时 basis 完整的矛盾。
- P3 测试覆盖：
  - 宏观顺风 + BTC 相对弱 => `btc_lagging_macro` 或 `btc_rejecting_macro_tailwind`。
  - 宏观逆风 + BTC residual 正 => `btc_resisting_macro_headwind`。
  - 缺少 BTC 或权益市场数据 => `missing` 且包含 `missing_reason`。
- P4.5 / API / UI 能展示状态或缺失原因。

## 验证建议

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py backend\tests\test_p45_dashboard_api.py -q
npm run build
```
