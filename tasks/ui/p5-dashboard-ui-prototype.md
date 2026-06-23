# P5 Dashboard UI 原型文档

## 版本

- 版本：v1
- 日期：2026-05-22
- 范围：P5 Dashboard 首屏，不包含完整子页面实现。
- 对齐任务卡：P5-C01、P5-C02、P5-C03、P5-C04、P5-C05、P5-C07、P5-C25、P9-C02、P9-C10。

## 设计定位

Dashboard 是 onlyBTC 的实时研究总控台。它不是交易终端，也不是营销页。

首屏需要回答五个问题：

1. 当前 BTC 最终判断是什么。
2. 这个判断来自哪些 Radar 模块。
3. 哪些数据或事件正在约束判断。
4. 本轮 P1/P2/P3/P4.5/LLM 链条是否健康。
5. 用户下一步应该看 Evidence、Article、Alerts、Data Quality 还是 Run Logs。

## 当前架构契约

Dashboard 主数据源来自 P4.5 Report v2，不再使用 legacy P4 Agent/Debate 作为主裁判。

主 API：

- `GET /api/p45/dashboard/latest`
- `GET /api/p45/radar-modules/latest`
- `GET /api/data-quality/latest`
- `GET /api/p3/alerts/latest`
- `POST /api/p45/run-full-with-llm`
- `GET /api/p45/audit-reports/latest`

Dashboard 必须保留同 run 追溯链：

- `collect_run_id`
- `p2_radar_run_id`
- `p3_run_id`
- `pack_id`
- `article_run_id`
- `final_run_id`
- `llm_research_run_id`
- `llm_analyst_run_id`
- `run_mode`
- `runtime_mode`
- `llm_runtime_mode`

## 信息架构

```text
Top Bar
├── 系统名 / 当前 BTC 价格 / 24h 变化
├── final_view / alert level / data quality
├── last updated / Run Once / Audit Reports

Main Dashboard
├── 左侧导航 rail
├── 中央 BTC Decision Node
├── 14 个 Radar Module 节点
├── 24h / 3d / 7d 周期视图
├── 当前预警与反证/确认规则摘要
├── P4.5 LLM 附录状态摘要
└── 右侧详情抽屉入口
```

## 首屏布局

桌面端采用高密度暗色研究终端布局：

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Top Bar: onlyBTC / BTC / final_view / alert / data quality / Run Once        │
├───────┬───────────────────────────────────────────────┬──────────────────────┤
│ Nav   │                 Topology Canvas                │ Right Summary         │
│ Rail  │                                               │ Decision / LLM / DQ   │
│       │      Radar nodes around BTC decision node      │                      │
├───────┴───────────────────────────────┬───────────────┴──────────────────────┤
│ Horizon Views 24h / 3d / 7d            │ Alerts / Watch / Confirmation Rules  │
└────────────────────────────────────────┴──────────────────────────────────────┘
```

移动端不强制展示完整拓扑，改为：

1. BTC Decision Card
2. Horizon Cards
3. Radar Module 列表
4. Alerts / Data Quality
5. Run Context

## 左侧导航 Rail

左侧导航需要显示完整短标签，不使用单字缩写。每个标签控制在 2-4 个中文字内，避免用户只能猜含义。

推荐标签：

- 拓扑
- 雷达
- 证据
- 预警
- 质检
- 日志
- 回放
- 设置

Rail 宽度以能容纳 4 个中文字为准，桌面端推荐 88-96px。当前页面高保真采用 92px。移动端隐藏 rail，改为抽屉或底部导航。

## 顶部栏

字段：

- `onlyBTC`
- BTC 价格与 24h 变化
- `final_view_cn`
- `alert_level`
- `contract_validation.status`
- `data_quality_level`
- 最近更新时间
- `Run Once`
- `Audit Reports`

Run Once 状态：

- idle：`Run Full Chain`
- running：显示当前阶段
- completed：显示完成时间
- completed_with_llm_errors：主报告完成，LLM 附录降级
- failed：展示失败阶段并允许跳转 Run Logs

Run Once 点击后打开 Run Logs 抽屉，并定位当前 run。

Audit Reports 点击后打开本轮审计报告索引，展示 P1/P2/P3/P4.5 HTML 报告链接。HTML 报告只用于人类审计查看，不作为 Vue3 数据源解析。

## BTC 中心节点

主状态只来自 P4.5：

| UI 字段 | 数据字段 |
|---|---|
| 状态 | `final_view_cn` |
| 强度 | `decision_card.strength_cn` |
| 置信度 | `decision_card.confidence` / `confidence_level` |
| 风险模式 | `decision_card.risk_mode` |
| 发布许可 | `decision_card.trade_permission` |
| 一句话结论 | `decision_card.conclusion_sentence` |
| 为什么不是强单边 | `decision_card.why_not_strong` |

视觉规则：

- neutral：灰蓝边框，稳定态。
- weak_bullish / bullish：青绿色边框和支撑线。
- weak_bearish / bearish：红色边框和压力线。
- mixed：黄色虚线边框。
- data_quality warning：紫色角标。
- warning / critical 才允许闪耀，且闪耀必须短暂克制。

中心节点禁止展示买入、卖出、仓位、杠杆、止损、止盈。

## Radar 模块节点

必须展示 14 个 P2 Radar module。

节点字段：

- `radar_module`
- `module_score`
- `module_direction`
- `module_strength`
- `module_confidence`
- `module_quality_score`
- positive / negative / zero / unavailable count
- top support drivers
- top pressure drivers
- `data_boundary`

节点点击：

- 单击 Radar 节点：打开 Radar Detail。
- 点击节点中的 evidence 数字：打开 Evidence，并筛选该 module。
- 点击 data quality 点：打开 Data Quality，并筛选上游 source。

连线规则：

- support：青绿色实线。
- pressure：红色实线。
- mixed：黄色虚线。
- stale / fallback：紫色虚线。
- strength 越高，线越粗。

默认只强调 dominant drivers、active warnings 和 degraded data sources。

## 周期视图

Dashboard 必须展示 24h / 3d / 7d 三个周期卡。

字段：

- `horizon`
- `direction`
- `strength`
- `confidence`
- support drivers
- pressure drivers
- watch rules

文案规则：

- 若 direction 偏多，只把 support drivers 写成主因，pressure drivers 单独写成约束。
- 若 direction 偏空，只把 pressure drivers 写成主因，support drivers 单独写成缓冲。
- 若 direction 中性或 mixed，必须同时说明支撑与压力。

## Alerts / 反证 / 确认规则

Dashboard 首屏显示：

- 当前最高 alert。
- active alerts 数量。
- 冷却期状态。
- top invalidation rules。
- top confirmation rules。

反证/确认规则不得被表现为交易动作。它们只是“什么会改变系统观察结论”的条件。

## LLM 附录状态

P4.5 已将 LLM 降为研究附录和内部参考，不再作为主裁判。

首屏只展示：

- DeepSeek research status
- 四分析师 LLM status
- `llm_runtime_mode`
- `completed` / `completed_with_llm_errors`
- `internal_reference` 标签

不在首屏展示长篇 LLM 文章，不展示 raw evidence id。

## 右侧详情抽屉

抽屉 Tab：

- Overview
- Article
- Radar
- Evidence
- Alerts
- Invalidation
- Data Quality
- LLM Appendix
- Run Logs

点击映射：

| 点击对象 | 打开 Tab |
|---|---|
| BTC 中心节点 | Overview |
| BTC 一句话结论 | Article |
| Radar 节点 | Radar |
| Evidence chip | Evidence |
| Alert 卡 | Alerts |
| 反证/确认条件 | Invalidation |
| Data Quality 状态 | Data Quality |
| LLM 状态 | LLM Appendix |
| Run Once | Run Logs |
| Audit Reports | Run Logs / Audit Reports 区块 |

## 高保真视觉规范

颜色：

- 背景：`#081017`
- 面板：`#0E1A23`
- 次级面板：`#122432`
- 边框：`#244050`
- 主文字：`#EAF5FF`
- 次文字：`#8FA7B8`
- bullish：`#22D3B6`
- bearish：`#F87171`
- neutral：`#9CA3AF`
- mixed / watch：`#FBBF24`
- warning：`#FB923C`
- critical：`#EF4444`
- data quality：`#A78BFA`

字体：

- `Inter`, `IBM Plex Sans`, `system-ui`
- 数字使用 `font-variant-numeric: tabular-nums`
- 不使用 viewport 宽度缩放字号。

交互：

- 研究终端感，低动效。
- hover 可高亮线条和节点。
- 不使用营销 hero、大面积渐变、装饰性光球。

## Dashboard DoD

- 首屏能看到 `final_view`、`decision_card`、`contract_validation.status`。
- 14 个 Radar module 全量展示。
- 每个 Radar 节点可下钻到对应 module detail。
- 24h / 3d / 7d 周期视图存在。
- Alerts / invalidation / confirmation rules 可见。
- LLM 明确标记为 `internal_reference`。
- Run Once 入口走 P4.5 full chain。
- Dashboard 提供 `Audit Reports` 入口，可打开同 run 的 P1/P2/P3/P4.5 原始 HTML 报告。
- 页面可以展示完整 run lineage。
- 不出现买卖、仓位、杠杆、止损、止盈语言。

## 高保真参考文件

- [P5 Dashboard High Fidelity](../../ui-references/p5-dashboard-high-fidelity.html)
