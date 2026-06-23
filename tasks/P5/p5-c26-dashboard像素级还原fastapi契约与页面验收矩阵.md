# P5-C26 Dashboard 像素级还原、FastAPI 契约与页面验收矩阵

## 状态

DONE

## 所属 Phase

P5 Dashboard 与可视化层

## 任务目标

建立 Dashboard 页面级实现总控卡：以 `ui-references/p5-dashboard-high-fidelity.html` 为高保真基准，在 Vue3 中进行像素级还原，并通过 P9 FastAPI 聚合接口打通真实 P1/P2/P3/P4.5 数据链路。

本卡不替代 P5-C01/P5-C02/P5-C03/P5-C07/P5-C20/P5-C25，而是作为这些 Dashboard 任务的统一验收矩阵。

## UI 基准

- UI 原型文档：[tasks/ui/p5-dashboard-ui-prototype.md](../ui/p5-dashboard-ui-prototype.md)
- 高保真参考：[ui-references/p5-dashboard-high-fidelity.html](../../ui-references/p5-dashboard-high-fidelity.html)
- 子页面高保真参考：[ui-references/p5-subpages-high-fidelity.html](../../ui-references/p5-subpages-high-fidelity.html)

## FastAPI 契约

Dashboard 首屏必须通过 P9 聚合 API 获取数据，不直接读取 SQLite，不解析 HTML 报告作为数据源。

必接接口：

- `GET /api/p45/dashboard/latest`
- `GET /api/p45/overview/latest`
- `GET /api/p45/radar-modules/latest`
- `GET /api/p45/radar-modules/{module_id}`
- `GET /api/p3/alerts/latest`
- `GET /api/p45/invalidation/latest`
- `GET /api/data-quality/latest`
- `GET /api/p45/audit-reports/latest`
- `GET /api/p45/runs/latest`
- `POST /api/p45/run-full-with-llm`
- `GET /reports/{report_html}`

可选增强接口：

- `GET /api/p45/articles/latest`
- `GET /api/p45/evidence`
- `GET /api/p45/analysts/latest`
- `GET /api/p45/llm/latest`
- `GET /api/settings`

## 像素级还原要求

- Vue3 Dashboard 首屏必须还原高保真中的三栏布局：`Top Bar + 左侧 Rail + Topology Canvas + Right Summary`。
- 桌面端基准视口：`1440x900`、`1920x1080`。
- 移动端基准视口：`390x844`。
- 左侧 Rail 宽度需容纳 2-4 个中文字标签，不允许出现单字纵向截断。
- 首屏必须展示 14 个 Radar module 节点、BTC 中心节点、周期卡、预警/反证/确认摘要、Run lineage、LLM internal_reference 状态。
- 颜色、间距、圆角、字体、边框、卡片密度以高保真文件为准；允许因真实数据长度做响应式微调，但不得破坏信息架构。
- 不允许营销式 hero、不允许装饰性渐变光球、不允许卡片套卡片。

## 页面交互矩阵

| 点击对象 | 目标 |
|---|---|
| BTC 中心节点 | Overview 抽屉 / `/overview` |
| View Overview | BTC Overview 页面 |
| Read Article | Article 页面 |
| Radar 节点 | Radar Detail 抽屉 / 页面，携带 `module_id` |
| Evidence chip | Evidence 页面，携带 `module_id` / `evidence_id` |
| Alert 卡 | Alerts 页面 |
| Invalidation / Confirmation 规则 | Invalidation 页面 |
| Data Quality 状态 | Data Quality 页面 |
| LLM 状态 | LLM Appendix / Analyst 页面，标记 `internal_reference` |
| Run Full Chain | 打开 Run Logs 抽屉并触发 P4.5 全链条 |
| Audit Reports | 打开本轮 P1/P2/P3/P4.5 HTML 审计报告索引 |
| Settings | Settings 页面 |

## 数据展示要求

- 主结论唯一来源：P4.5 `final_view` / `decision_card`。
- 旧 P4 Agent/Debate 只能作为 `legacy_p4_reference` 或内部附录，不得进入主裁判链。
- HTML 审计报告只能作为链接打开，不能由 Vue3 解析为页面数据源；报告链接必须优先使用 FastAPI 只读 `/reports/{report_html}`，避免浏览器拦截 `file://`。
- Dashboard 必须显示同 run lineage：`collect_run_id`、`p2_radar_run_id`、`p3_run_id`、`pack_id`、`article_run_id`、`final_run_id`、`llm_research_run_id`、`llm_analyst_run_id`。
- 质量字段必须可见：`contract_validation.status`、`data_quality_level`、`collection_freshness_status`、`business_recency_status`、`fallback_used`、`source_resolution`、`llm_runtime_mode`。

## 验收标准

- `npm run build` 通过。
- `scripts/validate_p5_dashboard_contract.py` 通过。
- Dashboard API smoke test 通过，至少覆盖 P5 首屏所需接口。
- Playwright 截图验收生成：
  - `screenshots/p5-dashboard-1440.png`
  - `screenshots/p5-dashboard-1920.png`
  - `screenshots/p5-dashboard-mobile.png`
- 截图中不得出现文字重叠、左侧 Rail 单字截断、卡片溢出、按钮文字挤压。
- 14 个 Radar module 全量出现，数量和 API 返回一致。
- Run Full Chain 与 Audit Reports 链路可点击。
- Dashboard 能从真实 FastAPI 数据渲染，mock 只允许用于测试 fixture。
- 不出现买入、卖出、仓位、杠杆、止损、止盈等交易执行语言。

## 本卡产物（2026-05-22）

- 新增验收矩阵：[tasks/ui/p5-dashboard-acceptance-matrix.md](../ui/p5-dashboard-acceptance-matrix.md)
- 新增静态契约检查脚本：[scripts/validate_p5_dashboard_contract.py](../../scripts/validate_p5_dashboard_contract.py)
- P5-C20 已提供统一 API client/store，本卡负责把后续 Dashboard 页面实现的 UI、接口、截图、禁止项收成统一闸门。

## 验证记录（2026-05-22）

- `.\.venv\Scripts\python.exe scripts\validate_p5_dashboard_contract.py`：通过。
- `npm run build`：通过。
- `.\.venv\Scripts\python.exe -m pytest backend/tests/test_p45_dashboard_api.py backend/tests/test_p45_full_chain_with_llm.py backend/tests/test_api.py -q`：通过。

说明：P5-C26 是验收基线卡，不负责最终 Vue 像素级页面实现。实际截图文件 `screenshots/p5-dashboard-1440.png`、`screenshots/p5-dashboard-1920.png`、`screenshots/p5-dashboard-mobile.png` 将在 P5-C01/P5-C02/P5-C03 页面实现阶段生成并纳入本矩阵复验。

## 依赖任务

P5-C01、P5-C02、P5-C03、P5-C07、P5-C20、P5-C25、P9-C02、P9-C05、P9-C06、P9-C07、P9-C08

## 备注

后续每个 P5 页面进入实现前，都需要先对齐 UI 原型、高保真文件、FastAPI endpoint、运行截图和 DoD。Dashboard 是第一张页面，按本卡作为标准样板。
