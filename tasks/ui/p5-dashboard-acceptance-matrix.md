# P5 Dashboard Acceptance Matrix

## 范围

本矩阵服务于 P5-C26，并作为后续 P5-C01 / P5-C02 / P5-C03 / P5-C04 / P5-C05 / P5-C07 的页面验收入口。

Dashboard 页面必须以 `ui-references/p5-dashboard-high-fidelity.html` 为视觉基准，以 P9 FastAPI 聚合接口为唯一生产数据源。

## 视口与截图

| 场景 | 视口 | 输出 |
|---|---:|---|
| desktop standard | `1440x900` | `screenshots/p5-dashboard-1440.png` |
| desktop wide | `1920x1080` | `screenshots/p5-dashboard-1920.png` |
| mobile | `390x844` | `screenshots/p5-dashboard-mobile.png` |

截图必须检查：

- 左侧 Rail 标签完整显示，不允许单字纵向截断。
- Top Bar 按钮不挤压，`Run Full Chain`、`Audit Reports`、`Settings` 可见。
- BTC 中心节点、Radar 节点、周期卡、右侧 Summary 不重叠。
- 移动端不强制展示完整拓扑，但必须保留 Decision / Horizon / Radar / Alerts / Run Context 的访问路径。

## FastAPI Smoke Matrix

| 页面区块 | Method | Endpoint | 必要字段 |
|---|---|---|---|
| Dashboard shell | GET | `/api/p45/dashboard/latest` | `final_view`, `decision_card`, `run_lineage`, `radar_modules` |
| BTC node | GET | `/api/p45/overview/latest` | `decision_card`, `aggregation_audit`, `horizon_views` |
| Radar nodes | GET | `/api/p45/radar-modules/latest` | `modules`, `count` |
| Radar detail | GET | `/api/p45/radar-modules/{module_id}` | `module`, `metrics` |
| Alerts | GET | `/api/p3/alerts/latest` | `alerts` |
| Invalidation | GET | `/api/p45/invalidation/latest` | `invalidation_rules`, `confirmation_rules` |
| Data quality | GET | `/api/data-quality/latest` | `source_health`, `contract_validation` |
| Audit reports | GET | `/api/p45/audit-reports/latest` | `reports` |
| Report HTML | GET | `/reports/{report_html}` | P1/P2/P3/P4.5 HTML |
| Runs | GET | `/api/p45/runs/latest` | `latest`, `stages` |
| Run once | POST | `/api/p45/run-full-with-llm` | `run_id` or `status` |

## Navigation Matrix

| Rail label | Route / Page id | 说明 |
|---|---|---|
| 拓扑 | `topology` | Dashboard 主拓扑 |
| 雷达 | `radar` | Radar module 列表与详情 |
| 证据 | `evidence` | Evidence 列表与详情 |
| 预警 | `alerts` | P3 alerts |
| 质检 | `quality` | Data quality |
| 日志 | `logs` | Run logs / audit reports |
| 回放 | `history` | History replay |
| 设置 | `settings` | Settings |

## 禁止项

页面正文与按钮不允许出现以下交易执行语言：

- 买入
- 卖出
- 开仓
- 止损
- 止盈
- 杠杆
- 仓位

允许出现“观察”“反证”“确认”“风险”“质量”“回放”“审计”等系统状态语言。

## DoD

- `scripts/validate_p5_dashboard_contract.py` 通过。
- `npm run build` 通过。
- FastAPI 相关测试通过。
- P1/P2/P3/P4.5 HTML 审计报告可通过 FastAPI `/reports/` 打开，不回退到 Dashboard SPA。
- P5-C01 开始后，必须补齐 Playwright 截图并保存到本矩阵规定路径。
