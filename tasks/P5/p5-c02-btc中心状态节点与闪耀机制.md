# P5-C02 BTC 中心状态节点与闪耀机制

## 状态

DONE

## 当前架构对齐（2026-05-22）

BTC 中心节点的主状态来自 P4.5 `decision_card`，不是旧 P4 state machine。

字段映射：状态=`final_view_cn`，强度=`decision_card.strength_cn`，置信度=`decision_card.confidence / confidence_level`，风险模式=`decision_card.risk_mode`，观察级许可=`decision_card.trade_permission`，一句话结论=`decision_card.conclusion_sentence`，周期节奏=`horizon_views`，强单边反证=`decision_card.why_not_strong`。

节点闪耀规则只用于 warning / critical / data_quality_bad 可视提示。`watch_only` 只能表达观察级发布，不得展示为交易动作。

## UI / 高保真对齐（2026-05-22）

BTC 中心节点必须像素对齐 `ui-references/p5-dashboard-high-fidelity.html` 中的 `.btc-node`：

- 标题区显示 `BTC`、`final_view_cn`、`trade_permission`。
- 右上 score ring 显示 confidence 百分比，不显示小数。
- 中部显示 `decision_card.conclusion_sentence` 的中文短句。
- 四宫格显示 `strength`、`risk_mode`、`24h`、`3d / 7d`。
- 下方保留 `View Overview`、`Read Article` 两个入口。
- 状态颜色来自 `final_view`，质量角标来自 `data_quality_level` / `contract_validation.status`。

## 所属 Phase

P5

## 任务目标

实现 BTC 中心状态节点，展示 P4 Final Controller 的当前状态、置信度、风险状态、发布约束、反证状态和数据质量约束。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 显示 `trend_state`、`risk_state`、`confidence`、`consensus_level`、`disagreement_level`、`publish_allowed`、`blocked_by`。
- 闪耀/强调机制只响应 P3/P4 预警等级与状态切换，不响应价格涨跌本身。
- 节点必须展示 confidence cap、fallback/runtime integrity 和关键反证摘要。
- 遵守 evidence + data、历史窗口、数据质量、反证机制和预警边界。
- 不输出交易建议，不引入开仓、止损、仓位或杠杆逻辑。

## 输入

- P9-C02 `GET /api/p45/overview/latest`
- P9-C02 `GET /api/p45/dashboard/latest`
- P4.5 decision_card / aggregation_audit / horizon_views
- P3 alert level 与 invalidation 状态

## 输出

- 可运行或可复用的代码、配置、Schema、接口、组件或文档。
- 必要的测试、验证记录或运行说明。

## 验收标准

- 与《开发文档.md》的总体架构一致。
- 中心节点能解释“为什么现在是这个状态”，并能跳转到 Overview / Evidence / LLM Appendix。
- 中心节点视觉与高保真 `.btc-node` 对齐，`1440x900` 与 `390x844` 截图无文字溢出。
- `why_not_strong` 至少展示摘要或提供跳转，不允许为空白占位。
- 不允许把 `watch_only` 渲染成买卖或仓位动作。
- 关键状态、错误、数据质量和 runtime fallback 可观测。
- 不绕过 P4.5 final_view、反证/确认规则、预警等级或数据质量约束。

## 依赖任务

P4-C18、P5-C09、P5-C25、P5-C26、P9-C02

## 备注

中心节点只表达系统状态与观察风险，不承载交易动作。

## 执行记录（2026-05-22）

- 已将 BTC 中心节点主状态切到 P4.5 `decision_card` / `final_view` / `horizon_views`。
- 已补齐 confidence score ring 真实进度、`quality` 与 `contract` 状态角标。
- 已接入 warning / critical / data quality bad 的闪耀提示；`watch_only` 仅作为观察级发布状态展示。
- 已展示 `why_not_strong` 摘要、反证规则入口、确认规则入口。
- 已补齐 `View Overview`、`Read Article`、`Evidence`、`LLM` 四个下钻入口。
- 已按桌面与移动端分别调整中心节点尺寸、score ring、文字换行与拓扑内圈节点避让。

## 验证记录（2026-05-22）

- `npm run build`：通过。
- `python scripts/validate_p5_dashboard_contract.py`：通过。
- 已生成截图：
  - `screenshots/p5-dashboard-c02-1440.png`
  - `screenshots/p5-dashboard-c02-mobile.png`

## DoD 结果

通过。中心 BTC 节点已能解释当前状态、展示关键约束并跳转 Overview / Article / Evidence / LLM Appendix。下一步由 P5-C03 继续收口 14 个 Radar 节点的语义排序、重叠避让与 module 细节。
