# P5 子页面 UI 原型文档

## 版本

- 版本：v1
- 日期：2026-05-22
- 范围：P5 Dashboard 子页面、右侧抽屉、全屏视图和跨页面跳转。
- 对齐任务卡：P5-C09 至 P5-C19、P5-C22、P5-C24、P5-C25。

## 设计原则

P5 子页面不是独立割裂的页面，而是 Dashboard 的下钻解释层。所有页面都必须保留同一套 run context，并能回到 Dashboard。

页面之间的跳转目标：

- 从 Dashboard 快速感知。
- 从子页面解释证据、来源、规则、质量和运行链路。
- 从任何 Evidence / Radar / Source / Alert / LLM 节点，都能继续下钻到相关页面。
- 历史模式和实时模式必须隔离，不允许实时推送覆盖历史回放。

## 统一路由与入口

正式 Vue3 路由建议：

| 页面 | 路由 | 任务卡 | 主 API |
|---|---|---|---|
| Dashboard | `/dashboard` | P5-C01 | `GET /api/p45/dashboard/latest` |
| BTC Overview | `/overview` | P5-C09 | `GET /api/p45/overview/latest` |
| Article | `/article` | P5-C08 | `GET /api/p45/articles/latest` |
| Evidence | `/evidence` | P5-C10 | `GET /api/p45/evidence` |
| LLM Appendix | `/llm` | P5-C11 | `GET /api/p45/llm/latest` |
| Alerts | `/alerts` | P5-C12 | `GET /api/p3/alerts/latest` |
| Invalidation | `/invalidation` | P5-C13 | `GET /api/p45/invalidation/latest` |
| Data Quality | `/data-quality` | P5-C14 | `GET /api/data-quality/latest` |
| Run Logs | `/run-logs` | P5-C15 | `GET /api/p45/runs/latest` |
| Audit Reports | `/run-logs#audit-reports` | P5-C07/P5-C15 | `GET /api/p45/audit-reports/latest` |
| Source Detail | `/sources/:source_id` | P5-C16 | `GET /api/sources/{source_id}` |
| Radar Detail | `/radars/:module_id` | P5-C17 | `GET /api/p45/radar-modules/{module_id}` |
| History Replay | `/history` | P5-C18 | `GET /api/p45/history` |
| Settings | `/settings` | P5-C22 | `GET /api/settings` |

高保真参考使用单个 HTML 文件 + hash anchors 模拟路由：

- [P5 Subpages High Fidelity](../../ui-references/p5-subpages-high-fidelity.html)

## 全局页面骨架

所有子页面使用同一骨架：

```text
Top Bar
├── onlyBTC / 当前或历史模式 / final_view / run context / 返回 Dashboard

Left Rail
├── 拓扑 / 概览 / 文章 / 证据 / 雷达 / 预警 / 反证 / 质检 / 日志 / 回放 / 设置

Main Page
├── Page Header
├── Key Summary Cards
├── Main Data Area
└── Audit / JSON / Run Lineage
```

左侧导航标签必须完整显示，控制在 2-4 个中文字内。

## 统一 run context

每个页面顶部或侧栏必须显示：

- `collect_run_id`
- `p2_radar_run_id`
- `p3_run_id`
- `pack_id`
- `final_run_id`
- `run_mode`
- `runtime_mode`
- `llm_runtime_mode`

页面跳转必须携带：

- `final_run_id`
- `pack_id`
- `module_id`
- `evidence_id`
- `source_id`
- `alert_id`
- `rule_id`
- `analyst_id`

## 页面设计

### BTC Overview

目的：解释当前 BTC 总控判断。

核心区块：

- Current Decision
- Decision Card
- 24h / 3d / 7d Horizon Views
- Support Drivers
- Pressure Drivers
- Why Not Strong
- Score Normalization
- Watch Next
- Run Lineage

跳转：

- driver chip -> Evidence
- rule chip -> Invalidation
- module chip -> Radar Detail
- quality chip -> Data Quality

### Article

目的：展示 P4.5 研究文章与发文版本。

核心区块：

- Research Article
- Publish Article
- Data Boundary
- Contract Validation
- LLM Research metadata
- Evidence Appendix link

约束：

- 主阅读区禁止 raw evidence id。
- Evidence id 只放在折叠审计附录。
- 不出现买卖、仓位、杠杆、止损、止盈语言。

### Evidence

目的：展示 claim / data / interpretation。

核心区块：

- Module filter
- Evidence list
- Evidence detail
- Metric score / effective score
- Freshness / horizon / duplicate weights
- Source health
- Source conflict

无 data 的 claim 不展示为正文结论，只能作为 data boundary。

### LLM Appendix

目的：展示 DeepSeek Research Writer 与四分析师 LLM 输出。

核心区块：

- LLM Runtime Summary
- Research Writer Article
- Macro / Liquidity / Microstructure / On-chain Analyst Articles
- Evidence Coverage
- Provider / model / latency / errors
- `internal_reference` 标签

旧 P4 Debate 如果展示，必须折叠并标记 `legacy_p4_debate`。

### Alerts

目的：展示 P3 预警和运营状态。

核心区块：

- Active Alerts
- Event Windows
- Cooldown / Debounce
- Supporting Evidence
- Conflicting Evidence
- Upgrade / Downgrade Conditions
- Alert Validity

人工动作只影响通知状态，不改原始审计记录。

### Invalidation

目的：展示反证条件和确认条件。

核心区块：

- Current final_view
- Invalidation Rules
- Confirmation Rules
- Rule Conditions
- Current Distance
- Action If Triggered
- Related Evidence / Alerts

规则必须同时有人类可读表达和机器可读条件。

### Data Quality

目的：统一展示 P1/P2/P3/P4.5 的质量边界。

核心区块：

- Overall Quality
- Contract Validation
- Source Health
- Freshness vs Business Recency
- Fallbacks
- Multi-source Conflicts
- Run Mode Integrity
- LLM Runtime Status

`MISSING_FRESHNESS_FIELDS` 若仅来自 unavailable 指标，显示为 warning，不阻塞。

### Run Logs

目的：展示 P4.5 full chain 运行审计。

核心阶段：

- P1 collect
- P2 radar
- P3 algorithm / scored evidence
- P4.5 evidence pack
- P4.5 deterministic final
- LLM research
- LLM analysts
- HTML / API refresh

Audit Reports 区块：

- P1 数据审计 HTML
- P2 Radar 质检 HTML
- P3 Algorithm Audit HTML
- P4.5 Research Report HTML
- 可选 GPT independent validation HTML

报告链接只用于打开原始审计产物，不作为前端结构化数据源。

LLM 失败时展示 `completed_with_llm_errors`，并说明 deterministic 主报告仍可用。

### Radar Detail

目的：解释单个 Radar module 的评分、证据和上游来源。

核心区块：

- Module Header
- Module Summary
- Feature Calculation
- Support / Pressure Drivers
- Metrics Table
- Evidence Summary
- Invalidation Signals
- Upstream Sources
- Module JSON

禁止只展示 signal，不展示评分来源。

### Source Detail

目的：解释单个 source 的健康、fallback、raw/normalized 数据和下游影响。

核心区块：

- Source Profile
- Latest Source Run
- Collection Freshness
- Business Recency
- Raw Observation Preview
- Normalized Metrics
- Fallback Chain
- Recent Errors
- Affected Modules / Evidence

raw response 必须脱敏。

### History Replay

目的：回放历史 P4.5 final_run。这里的“回放”不是回复消息，而是查看历史 run 的完整记录、当时的 Dashboard 状态、当时的证据包、当时生成的文章和后续有效性评分。

核心区块：

- Historical Mode Banner
- Timeline
- Frozen Dashboard Snapshot
- Historical Evidence / Article / LLM Links
- Signal Validity
- Alert Validity
- Confidence Calibration
- Run Artifacts / Audit Reports

历史回放默认不触发新 pipeline，只读取指定 `final_run_id` 的 frozen payload。页面必须明显标记 `historical mode`，避免用户误以为这是当前实时状态。

历史模式必须明显，不得误导为实时状态。

### Settings

目的：展示和管理运行配置，先只读为主。

核心区块：

- API Keys
- Data Sources
- P4.5 LLM Provider
- Run Once / Scheduler
- Alerts Policy
- Storage / Paths
- System

API key 必须脱敏，不能显示完整明文。

Settings 是独立子页面，不是弹窗。Dashboard 右上角 Settings 按钮进入该页；用户可以从 Settings 返回实时 Dashboard。早期实现可先只读展示配置，后续再逐步开放编辑、测试连接和保存。

## 点击链路矩阵

| 起点 | 目标 |
|---|---|
| Dashboard BTC 节点 | Overview |
| Dashboard 一句话结论 | Article |
| Dashboard Radar 节点 | Radar Detail |
| Radar Driver | Evidence |
| Evidence Source | Source Detail |
| Alert Card | Alerts Detail |
| Alert Evidence | Evidence |
| Invalidation Rule | Invalidation Detail |
| Data Quality Source Row | Source Detail |
| Run Stage | Run Logs Detail |
| History Snapshot | History Replay |
| Settings Gear | Settings |

## DoD

- 所有子页面都有对应高保真视图。
- 页面之间可通过链接互跳。
- 每个页面都保留 run context。
- 历史模式和实时模式视觉上区分。
- Evidence / Source / Radar / Alert / Run 可以相互定位。
- 页面不出现交易执行语言。
- LLM 页面明确标记 `internal_reference`，不作为最终裁判。
