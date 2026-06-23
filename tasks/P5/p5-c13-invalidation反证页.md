# P5-C13 Invalidation 反证页

## 状态

DONE

## 当前架构对齐

Invalidation 页主数据来自 P4.5 Report v2 的 `invalidation_rules`、`confirmation_rules`、`decision_card`、`horizon_views`，通过 `GET /api/p45/invalidation/latest` 和 Dashboard 已加载的 Evidence payload 展示规则、条件、当前指标状态和跳转入口。

## 所属 Phase

P5 Dashboard 与可视化层

## 任务目标

实现“反证 / 确认规则工作台”，让用户能看到当前 final view 为什么仍是观察态、哪些条件会把结论上修或降级、每条规则关联哪些指标和 Evidence。

## FastAPI 依赖

- `GET /api/p45/invalidation/latest`
- `GET /api/p45/evidence`
- `GET /api/p45/dashboard/latest`
- `GET /api/p3/alerts/latest`
- `GET /api/p45/runs/latest`

## 实施范围

- 顶部展示 final view、trade permission、反证规则数、确认规则数。
- 反证规则与确认规则分区展示。
- 每条规则展示 horizon、applies_when、action_if_triggered、reason、机器条件表达式。
- 每条规则展示关联 metric 的当前值、metric_score、effective score、direction、source。
- 提供 Evidence、Alerts、Run Logs 跳转入口。
- 不显示 Python dict / raw JSON 作为主阅读内容。

## 验收标准

- 页面能展示至少 3 条 invalidation rules 和至少 1 条 confirmation rule。
- 每条规则有可读条件表达式。
- 每条规则能看到关联 metric 当前状态，缺失时显示 `waiting evidence`。
- 页面可以跳转 Evidence / Alerts / Run Logs。
- `npm run build` 通过。
- `python scripts/validate_p5_dashboard_contract.py` 通过。
- `python scripts/validate_p5_page_dod.py` 通过。

## 完成记录

- Invalidation 页已升级为 `Invalidation / Confirmation Workbench`。
- 已展示 final view、trade permission、confidence、规则统计、run lineage。
- 反证规则和确认规则分栏展示，包含 horizon、action、reason、条件表达式和规则进度。
- 每条规则已展示关联 metric 的当前 Evidence 摘要：value、metric_score、direction，并可点击跳转 Evidence。
- 页面提供 Evidence、Alerts、Run Logs、Overview 快捷入口。
- 页面不直接展示 raw JSON / Python dict，规则条件使用可读表达式。

## 验收结果

- `npm run build` 通过。
- `python scripts/validate_p5_dashboard_contract.py` 通过。
- `python scripts/validate_p5_page_dod.py` 通过。
