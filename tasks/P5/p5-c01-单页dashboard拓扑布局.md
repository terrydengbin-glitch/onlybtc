# P5-C01 单页 Dashboard 拓扑布局

## 状态

DONE

## 当前架构对齐（2026-05-22）

本卡以 P4.5 Report v2 为 Dashboard 主输入。Dashboard 不再消费旧 P4 `dashboard_snapshots` 作为主裁判来源；旧 snapshot 只用于 history 或 legacy 兼容。

主页面读取：`GET /api/p45/dashboard/latest`、`GET /api/p45/radar-modules/latest`、`GET /api/data-quality/latest`。

首屏必须显示：`final_view`、`decision_card`、`horizon_views`、`contract_validation.status`、14 个 Radar module、完整 run lineage、DeepSeek LLM research 与四分析师 LLM 状态摘要。LLM 内容必须标记 `internal_reference`。

Run Once 入口必须触发 P4.5 全链条：`P1 -> P2 -> P3 -> P4.5 deterministic -> P4.5 LLM appendix -> HTML/API refresh`，不再调用旧 `/api/run-once` mock 作为生产入口。

## UI / 高保真对齐（2026-05-22）

本卡实现必须以 `ui-references/p5-dashboard-high-fidelity.html` 为像素级基准，并同步遵守 P5-C26 的页面验收矩阵。

必须还原：

- `Top Bar + 左侧 Rail + Topology Canvas + Right Summary` 三栏结构。
- 左侧 Rail 标签：`拓扑 / 雷达 / 证据 / 预警 / 质检 / 日志 / 回放 / 设置`，宽度必须容纳 2-4 个中文字，不允许单字纵向截断。
- 中央 BTC Decision Node 与 14 个 Radar module 节点的相对布局。
- 支撑/压力/mixed/data quality 连线视觉语义。
- 底部 24h / 3d / 7d 周期卡与 Alerts / Invalidation / Confirmation 摘要区。
- 右侧 Summary 中的 Decision、LLM Appendix、Data Quality、Run Lineage。

像素验收视口：`1440x900`、`1920x1080`、`390x844`。

## 所属 Phase

P5

## 任务目标

实现 P5 主 Dashboard 的单页拓扑布局，直接消费 P4.5 Report v2 与 P2/P3/P4.5 聚合状态。

主面板不再是静态 PPT 风格页面，必须能承载真实 run context、14 个 Radar module、P3 预警/反证、P4.5 final_view / decision_card、数据质量与 LLM appendix 状态。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 建立 Dashboard AppShell：中心 BTC 状态节点、14 个 Radar 拓扑节点、事件/预警/数据质量/Agent Runtime 摘要区。
- 页面顶部或运行摘要区显示本轮 `collect_run_id`、`p2_radar_run_id`、`p3_run_id`、`pack_id`、`final_run_id`、`llm_research_run_id`、`llm_analyst_run_id`、`run_mode`。
- 每个拓扑节点支持打开右侧详情抽屉，并保留点击上下文。
- 遵守 evidence + data、历史窗口、数据质量、反证机制和预警边界。
- 不输出交易建议，不引入开仓、止损、仓位或杠杆逻辑。

## 输入

- P9-C02 `GET /api/p45/dashboard/latest`
- P9-C02 `GET /api/p45/overview/latest`
- P9-C02 `GET /api/p45/radar-modules/latest`
- P9-C05 `GET /api/p3/alerts/latest`
- P9-C05 `GET /api/p45/invalidation/latest`
- P9-C06 `GET /api/data-quality/latest`
- P9-C07 `GET /api/p45/runs/latest`
- P9-C07 `GET /api/p45/audit-reports/latest`
- P4.5 Report v2 payload
- P2 14 个 Radar module 最新输出
- P3 alert / invalidation / event window 输出

## 输出

- 可运行或可复用的代码、配置、Schema、接口、组件或文档。
- 必要的测试、验证记录或运行说明。

## 验收标准

- 与《开发文档.md》的总体架构一致。
- Dashboard 能展示 P1/P2/P3/P4.5 同 run 追溯链。
- Dashboard 与 `ui-references/p5-dashboard-high-fidelity.html` 信息架构一致，并通过 Playwright 截图验收。
- 首屏 14 个 Radar module 与 API 返回数量一致，不允许前端写死遗漏。
- Run Full Chain、Audit Reports、Overview、Article、Radar、Evidence、Alerts、Quality、Runs、History、Settings 均可点击进入对应页面/抽屉。
- 关键状态、错误、数据质量、fallback、runtime integrity 可观测。
- 不绕过 P4.5 final_view、反证/确认规则、预警等级或数据质量约束。

## 依赖任务

P5-C20、P9-C02、P5-C25、P5-C26、P4-C18、P2-C21、P3-C14

## 备注

执行前先完成 P5-C25 对齐基线，并确认 P9-C02 返回字段覆盖本卡所需状态。

## 执行记录（2026-05-22）

- Vue3 Dashboard 主框架已按 `ui-references/p5-dashboard-high-fidelity.html` 重构为：Top Bar、8 项左侧 Rail、Topology Canvas、Right Summary、底部 Horizon / Watch 区。
- Topology 从圆形自动布局改为固定 14 点位布局，保留 P4.5 Report v2 标识、support/pressure/mixed/data quality 图例和连线语义。
- 右侧 Summary 已补齐：决策卡、Run Lineage、LLM internal_reference 四分析师卡、快捷入口。
- 移动端改为线性卡片布局，避免完整拓扑在窄屏挤压。

## 验证记录（2026-05-22）

- `npm run build`：通过。
- `.\.venv\Scripts\python.exe scripts\validate_p5_dashboard_contract.py`：通过。
- `.\.venv\Scripts\python.exe -m pytest backend/tests/test_p45_dashboard_api.py backend/tests/test_p45_full_chain_with_llm.py backend/tests/test_api.py -q`：通过。
- Playwright 截图已生成：
  - `screenshots/p5-dashboard-1440.png`
  - `screenshots/p5-dashboard-1920.png`
  - `screenshots/p5-dashboard-mobile.png`
- 1440 视口 `body.scrollWidth == viewport`，无整页横向爆版。

说明：本卡完成 Dashboard 主框架和入口功能还原。BTC 中心节点视觉细节继续由 P5-C02 收口，Radar 节点语义、排序、重叠与 module driver 细节继续由 P5-C03 收口。
