# P3-C25 Trend State 阈值校准与状态分布回测

## 状态

DONE

## Phase

P3 算法、事件窗口与评分层

## 背景

P3-C22/P3-C23/P3-C24 已完成指标评分语义、模块聚合器和 Radar 状态机。最新全链条审计显示：

```text
14 个 Radar module
trend_state:
  neutral_wait_confirm: 12
  conflict_no_trade: 2
```

模块层已经能识别 `support_dominant`、`pressure_dominant`、`bearish_but_improving`、`internal_conflict`，但最终 `trend_state` 仍大量落入 `neutral_wait_confirm`。这说明状态机阈值可能偏保守，导致 `bearish_pressure`、`bearish_but_improving`、`risk_on_confirmed` 等状态不够自然地出现。

## 目标

- 校准 `direction_score`、`risk_score`、`confidence_score`、`conflict_score` 与 `trend_state` 的映射阈值。
- 避免所有模块被过度压成 neutral。
- 保持谨慎，不把弱信号误判成强趋势。
- 通过历史 run 分布回测验证状态机是否更符合 BTC 趋势分析语义。

## 审计输入

- P3-C21 评分规则文档。
- P3-C22 高优先级指标规则。
- P3-C23 模块聚合字段：
  - `module_raw_score`
  - `module_final_score`
  - `coverage_score`
  - `conflict_score`
  - `module_confidence`
  - `top_contributors`
- P3-C24 状态机字段：
  - `direction_score`
  - `risk_score`
  - `confidence_score`
  - `freshness_score`
  - `module_state`
  - `trend_state`

## 优化方向

1. 对最近 N 次 P3 run 输出状态分布表。
2. 检查模块状态与 trend state 是否一致：
   - `pressure_dominant` 是否总被压成 neutral。
   - `support_dominant` 是否能自然出现 `risk_on_confirmed` 或弱支撑状态。
   - `bearish_but_improving` 是否能被保留到 trend_state。
3. 调整阈值：
   - 方向阈值不要只看绝对 `direction_score`。
   - 应结合 `module_state`、`top_contributors`、`risk_score`、`confidence_score`。
4. 增加回测报告：
   - 每个模块过去 N 次状态分布。
   - 状态变化原因。
   - 调整前后对比。

## DoD

- 生成状态机阈值审计报告。
- 至少覆盖最近 10 次 P3 run；如果不足 10 次，覆盖全部历史 run。
- 输出调整前/调整后的 trend_state 分布。
- `bearish_pressure`、`bearish_but_improving`、`risk_on_confirmed` 等状态能在合理样本中自然出现。
- 不破坏 P4.5/P5 现有字段契约。
- P1/P2/P3/P4.5 全链条重跑通过。

## 关联任务

P3-C21, P3-C22, P3-C23, P3-C24, P4.5-C11, P4.5-C12, P5-C03, P5-C17

## 执行记录

- 已调整 P3 Radar module 状态机阈值：
  - 保留强方向阈值 `±12` 作为强状态判断。
  - 新增上下文阈值：结合 `module_state`、`direction_score`、`risk_score`、`confidence_score` 与 `conflict_score` 判断状态。
  - `bearish_but_improving` 在模块状态已识别压力缓和时优先保留，不再被 raw/effective conflict 一律压成 `conflict_no_trade`。
  - `pressure_dominant` 且方向分低于 `-2`、置信度充足时可输出 `bearish_pressure`。
  - `support_dominant` 且方向分高于 `+4`、置信度充足时可输出 `risk_on_confirmed`。
- 新增审计脚本：

```text
scripts/audit_p3_trend_state_distribution.py
```

- 审计报告输出：

```text
reports/p3-trend-state-calibration-report.md
```

## 回测结果

最近 10 次 P3 scored module 的旧规则分布：

```text
neutral_wait_confirm: 136
conflict_no_trade: 4
```

校准后规则分布：

```text
neutral_wait_confirm: 127
conflict_no_trade: 4
bearish_pressure: 5
bearish_but_improving: 2
risk_on_confirmed: 2
```

本轮真实全链条 run：

```text
collect_run_id: collect-20260523062818-4677cf
p2_radar_run_id: radar-20260523062950-eba9a8
p3_run_id: p3-20260523062951-0beea2
final_run_id: p45final-20260523062953-584a62
```

本轮 P3 trend_state 分布：

```text
neutral_wait_confirm: 8
conflict_no_trade: 2
bearish_pressure: 3
bearish_but_improving: 1
```

本轮代表性模块：

```text
treasury_credit -> bearish_pressure
dollar_liquidity -> bearish_pressure
trade_structure_flow -> bearish_pressure
fund_flow -> bearish_but_improving
btc_total_state -> conflict_no_trade
onchain_valuation -> conflict_no_trade
```

## 验证结果

```text
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p3_pipeline.py -q
15 passed

.\.venv\Scripts\python.exe -m py_compile backend/src/onlybtc/algorithms/p3.py scripts/audit_p3_trend_state_distribution.py
passed

.\.venv\Scripts\python.exe -m onlybtc.cli p45-full-audit --run-mode live --runtime-mode deterministic
completed
```

输出报告：

```text
reports/p1-c22-真实数据全链路验收报告.html
reports/p2-radar-quality-report.html
reports/p3-algorithm-audit-report.html
reports/p45-research-report.html
reports/p3-trend-state-calibration-report.md
```
