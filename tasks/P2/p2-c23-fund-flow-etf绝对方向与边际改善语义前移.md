# P2-C23 Fund Flow ETF 绝对方向与边际改善语义前移

## 状态

DONE

## 所属 Phase

P2 Radar 指标与模块层

## 背景

最近一次真实链路审计发现，P3/P4.5 已经可以把资金流模块表达为：

- `fund_flow_absolute_direction = bearish`
- `fund_flow_marginal_direction = improving`
- `fund_flow_state = bearish_but_improving`

但 P2 的 Fund Flow 源头仍存在语义反向风险：

- `etf_net_flow < 0`
- `etf_flow_7d < 0`
- P2 feature 却可能显示 `direction = bullish`

这会误导 Dashboard、文章层、Evidence 解释和 LLM 输入。ETF 净流出减少只能代表“压力缓和”，不能代表“资金转多”。

## 目标

在 P2 层前移 Fund Flow 语义治理：

1. ETF 净流出不得显示为 bullish。
2. ETF 净流出只能表达为 bearish outflow。
3. ETF 流出收窄只能表达为 pressure_easing / improving。
4. Fund Flow 模块输出绝对方向、边际方向、冲突级别和复合状态。
5. P4.5 即使使用 exchange balance 作为支撑驱动，也必须保留 ETF outflow pressure note。

## 不改范围

- 不修改 P1 采集逻辑。
- 不改变 exchange_balance_delta_1d_proxy 的 bullish 解释。
- 不把 ETF 流出收窄直接当成 bullish。
- 不新增 Fund Flow 数据源。
- 不重写 P3/P4.5 现有聚合框架，只补契约字段和解释链路。

## P2 Schema 增量

Fund Flow module 增加：

```json
{
  "fund_flow_absolute_direction": "bearish|neutral|bullish",
  "fund_flow_marginal_direction": "worsening|stable|improving|strengthening|weakening",
  "fund_flow_conflict_level": "none|low|medium|high",
  "fund_flow_state": "bullish|bullish_but_weakening|neutral_mixed|bearish_but_improving|bearish"
}
```

ETF feature 增加：

```json
{
  "direction": "bearish|neutral|bullish",
  "flow_state": "bearish_outflow|neutral|bullish_inflow",
  "marginal_state": "pressure_easing|pressure_worsening|stable|null"
}
```

## 规则

### ETF Absolute Direction

```text
if etf_net_flow > 0:
    direction = bullish
    flow_state = bullish_inflow

elif etf_net_flow < 0:
    direction = bearish
    flow_state = bearish_outflow

else:
    direction = neutral
    flow_state = neutral
```

`etf_flow_7d` 同样遵守该绝对方向规则。

### ETF Marginal Direction

```text
if current_flow < 0 and outflow_abs_decreasing:
    marginal_state = pressure_easing
    marginal_direction = improving

elif current_flow < 0 and outflow_abs_increasing:
    marginal_state = pressure_worsening
    marginal_direction = worsening

elif current_flow > 0 and inflow_increasing:
    marginal_state = inflow_strengthening
    marginal_direction = strengthening

elif current_flow > 0 and inflow_decreasing:
    marginal_state = inflow_weakening
    marginal_direction = weakening
```

### Fund Flow State

```text
if absolute_direction == bearish and marginal_direction == improving:
    fund_flow_state = bearish_but_improving

elif absolute_direction == bullish and marginal_direction in [weakening, worsening]:
    fund_flow_state = bullish_but_weakening

elif absolute_direction == bearish and marginal_direction == worsening:
    fund_flow_state = bearish

elif absolute_direction == bullish and marginal_direction in [improving, strengthening]:
    fund_flow_state = bullish

else:
    fund_flow_state = neutral_mixed
```

## P4.5 增量

当 Fund Flow 是“绝对偏空但边际改善”时，P4.5 增加 `pressure_notes`：

```json
{
  "pressure_notes": [
    {
      "module": "fund_flow",
      "indicator": "etf_net_flow",
      "type": "absolute_pressure",
      "severity": "medium",
      "message": "ETF 仍处于净流出，绝对资金面偏空，但流出压力边际缓和。"
    }
  ]
}
```

触发条件：

```text
if fund_flow_absolute_direction == bearish
and fund_flow_marginal_direction == improving:
    add pressure note
```

## 验收样例

输入：

```json
{
  "etf_net_flow": -101467876,
  "etf_flow_7d": -1450852432,
  "exchange_balance_delta_1d_proxy": -2083,
  "stablecoin_supply": "偏弱"
}
```

P2 期望输出：

```json
{
  "fund_flow_absolute_direction": "bearish",
  "fund_flow_marginal_direction": "improving",
  "fund_flow_conflict_level": "high",
  "fund_flow_state": "bearish_but_improving",
  "features": {
    "etf_net_flow": {
      "direction": "bearish",
      "flow_state": "bearish_outflow",
      "marginal_state": "pressure_easing"
    },
    "etf_flow_7d": {
      "direction": "bearish",
      "flow_state": "bearish_outflow"
    },
    "exchange_balance_delta_1d_proxy": {
      "direction": "bullish"
    }
  }
}
```

## DoD

- `etf_net_flow < 0` 时，P2 不得输出 `direction = bullish`。
- `etf_flow_7d < 0` 时，P2 不得输出 `direction = bullish`。
- ETF 净流出收窄时，只能输出 `pressure_easing` / `improving`。
- P2 Fund Flow 必须输出 `absolute_direction` / `marginal_direction` / `conflict_level` / `state`。
- P3 能读取 P2 新字段，或在字段缺失时继续使用现有治理逻辑并输出 warning。
- P4.5 文章层和 Final JSON 保留 ETF outflow pressure note。
- 回归测试覆盖本轮样例，锁死“净流出显示 bullish”的问题。

## 实施记录

- P2 `fund_flow` 增加 ETF 专用 semantic overlay：
  - `etf_net_flow < 0` / `etf_flow_7d < 0` 固定为 `direction=bearish`。
  - `change_24h > 0` 且当前仍为负值时，输出 `marginal_state=pressure_easing`、`marginal_direction=improving`。
  - ETF 指标增加 `flow_state`、`marginal_state`、`marginal_direction`、`semantic_rule_id`。
- P2 `fund_flow` module 增加：
  - `fund_flow_absolute_direction`
  - `fund_flow_marginal_direction`
  - `fund_flow_conflict_level`
  - `fund_flow_state`
- P3 `fund_flow` module semantic profile 优先读取 P2 新字段；字段缺失时保留原 P3 fallback 推断。
- P4.5 Final JSON 增加 `pressure_notes`，并同步写入 `research_article.pressure_notes`。

## 测试结果

- `pytest backend/tests/test_radars.py::test_fund_flow_etf_outflow_is_not_marked_bullish -q`：通过。
- `pytest backend/tests/test_p45_final_writer.py::test_p45_final_writer_preserves_fund_flow_etf_pressure_note -q`：通过。
- `pytest backend/tests/test_radars.py backend/tests/test_p3_pipeline.py -q`：26 passed。
- `pytest backend/tests/test_p45_final_writer.py backend/tests/test_p45_evidence_pack.py backend/tests/test_p45_html_report.py backend/tests/test_p45_dashboard_api.py -q`：15 passed。

## 关联任务

- P2-C05
- P2-C22
- P3-C22
- P4.5-C20
- P4.5-C21
