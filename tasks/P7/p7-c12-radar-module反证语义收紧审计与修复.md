# P7-C12 Radar Module 反证语义收紧审计与修复

状态：DONE

## 背景

`Invalidation Workbench v2` 已经覆盖 14 个 radar modules，并且当前 latest payload 没有误触发 confirmation / refutation。

最新审计报告：

```text
reports/p7-c12-radar-invalidation-module-audit.md
reports/p7-c12-radar-invalidation-module-audit.json
```

审计结论为 `PASS_WITH_WARNINGS`，无阻断性问题，但发现部分模块的 `accepted evidence` 语义还需要收紧：

```text
asia_risk:
  evidence_state = accepted
  btc_implication = neutral
  signal_stage = none

btc_adoption:
  evidence_state = accepted
  btc_implication = neutral
  signal_stage = none

onchain_valuation:
  evidence_state = accepted
  btc_implication = neutral
  signal_stage = none

fund_flow:
  evidence_state = accepted
  data_quality_flags includes etf_single_source
```

这些并不是 mock 或漏链条问题，而是语义边界问题：有 response / residual 的 context evidence 可以参与背景判断，但不能表现得像强确认或强反证。

## 目标

收紧 `Invalidation Workbench v2` 对 14 个 radar modules 的反证语义，使页面和 payload 能明确区分：

```text
accepted_directional_evidence:
  可参与 confirmation / refutation 裁决

accepted_context_evidence:
  只能作为背景、压力或支撑，不允许单独触发

quality_discounted_evidence:
  有数据质量 flag，可参与但必须降权，并在 UI 明确标注

missing_or_unconfirmed_evidence:
  有方向但缺 BTC response / residual gate，不允许触发
```

核心原则：

```text
context accepted != directional accepted
neutral implication != triggerable refutation
data quality flagged evidence != full-strength accepted
single module cannot trigger confirmed/refuted
BTC response / residual gate remains mandatory
```

## 范围

### P4.5 Workbench

涉及文件：

```text
backend/src/onlybtc/p45/invalidation_workbench.py
backend/tests/test_p45_invalidation_workbench.py
```

要求：

1. `_evidence_state` 不再只根据 `accepted_status=accepted` 直接返回 `accepted`。
2. 新增可裁决证据与背景证据的判断：

```text
directional accepted:
  effective_direction in bullish/bearish
  and signal_stage in fast_signal/confirmed_signal/conflict
  or btc_implication is directional / rejection / confirmed
  or module is BTC response layer with strong btc_response_score

context accepted:
  effective_direction in bullish/bearish
  but btc_implication in neutral/empty
  and signal_stage = none
```

3. 对 context accepted 输出更保守的状态，例如：

```text
context
unconfirmed
accepted_context
```

具体命名以现有前端 `statusClass` 兼容为准，不能破坏旧页面。

4. 带 `data_quality_flags` 的 accepted evidence 必须输出 `quality_discounted` 或保留 `accepted` 但增加可消费字段：

```json
{
  "evidence_weight_status": "full|discounted|context|blocked",
  "trigger_eligible": false
}
```

5. `triggered_rules` 的生成必须只消费 `trigger_eligible=true` 的证据。

### P9 API

涉及文件：

```text
backend/src/onlybtc/api/p45_dashboard.py
frontend/src/api.ts
```

要求：

1. `/api/p45/invalidation/latest` 透传新增字段。
2. `/api/p45/history/{run_id}` replay 保留历史 payload，不被当前新规则重算污染。
3. 前端类型允许新增字段，不影响旧 payload fallback。

### P5 Frontend

涉及文件：

```text
frontend/src/App.vue
frontend/src/styles.css
```

要求：

1. Evidence Matrix 中区分：

```text
accepted
accepted_context / context
quality_discounted
missing
stale
blocked
conflict
rejected
```

2. context evidence 不使用强确认颜色。
3. quality discounted evidence 显示数据质量提示。
4. Workbench 顶部 validation banner 不被 context evidence 拉成 confirmed/refuted。

## DoD

1. 最新 run once 后 `invalidation_workbench.schema_version = p45.invalidation_workbench.v2`。
2. `module_evidence_matrix` 覆盖 14 个 radar modules。
3. `asia_risk / btc_adoption / onchain_valuation` 在 `btc_implication=neutral` 且 `signal_stage=none` 时不能显示为强 accepted。
4. `fund_flow` 在 `etf_single_source` 等 data quality flag 存在时必须被标记为 discounted 或 trigger ineligible。
5. `triggered_rules` 只允许由 `trigger_eligible=true` 的证据组合触发。
6. 当前 neutral/watch-only thesis 下：

```text
refute_current_view = []
break_neutral_scenarios exists
triggered_rules = []
validation_state in watching/conflict/blocked
```

7. 缺 BTC response 或 residual 时不允许 `triggered`。
8. 单一 module 不允许触发 confirmed/refuted。
9. 历史 replay 仍可读取旧 payload。
10. 以下命令通过：

```text
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_invalidation_workbench.py backend\tests\test_p45_btc_trend_cockpit.py -q
.\.venv\Scripts\python.exe scripts\validate_p5_dashboard_contract.py --base-url http://127.0.0.1:8118
npm run build
```

11. 生成新的审计报告：

```text
reports/p7-c12-radar-invalidation-module-audit.md
reports/p7-c12-radar-invalidation-module-audit.json
```

最终状态必须从 `PASS_WITH_WARNINGS` 收敛到 `PASS`，或明确记录剩余 warning 的业务原因。

## 完成记录

完成时间：2026-05-27

实现结果：

```text
P4.5 Workbench:
  新增 evidence_weight_status
  新增 trigger_eligible
  accepted_context / quality_discounted 不再参与 triggered 裁决

P5 Workbench:
  Evidence Matrix 展示 evidence_weight_status
  Evidence Matrix 展示 trigger eligible / context-gated 状态
  context / discounted 状态不再使用强确认颜色

最新 run once:
  final_run_id = p45final-20260527120852-bf4b06
  validation_state = watching
  triggered_rules = 0
  armed_rules = 3
```

最新审计：

```text
reports/p7-c12-radar-invalidation-module-audit.md
reports/p7-c12-radar-invalidation-module-audit.json
status = PASS
issues = 0
warnings = 0
```

验证命令：

```text
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_invalidation_workbench.py backend\tests\test_p45_btc_trend_cockpit.py -q
9 passed

npm run build
passed

.\.venv\Scripts\python.exe scripts\validate_p5_dashboard_contract.py --base-url http://127.0.0.1:8118
passed
```

## 非目标

```text
不重写 14 个 radar modules。
不改变 BTC Trend Cockpit 的主状态机。
不修改 radar 子页面布局。
不调整 P1/P2/P3 指标计算。
```
