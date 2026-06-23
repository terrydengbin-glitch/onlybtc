# P5-C12 Alerts 预警页

## 状态

DONE

## 当前架构对齐

Alerts 页消费 P3 alert / event / watch 输出，并结合 P4.5 的 final view、反证规则和确认规则提供运营观察入口。页面只通过 FastAPI 聚合接口读取数据，不直接解析 HTML 报告，不把 `publish_article` 文案误当作 alert。

## 所属 Phase

P5 Dashboard 与可视化层

## 任务目标

实现可读、可审计、可跳转的预警工作台，展示活跃预警、预警统计、run lineage、反证/确认条件、宏观事件窗口和减产背景。

## FastAPI 依赖

- `GET /api/p3/alerts/latest`
- `GET /api/p3/events/latest`
- `GET /api/p45/invalidation/latest`
- `GET /api/p45/evidence`
- `GET /api/p45/runs/latest`

## 实施范围

- Active Alerts：level / state / title / summary / cooldown / evidence count / updated_at。
- Alert Summary：active count、critical/warning/info 分布、cooling/active 状态、final view。
- Rule Linkage：反证规则与确认规则，并显示机器条件表达式。
- Event Window：展示 P3 宏观事件窗口、daily watch、source resolution。
- 操作入口：跳转 Evidence、Invalidation、Run Logs、Audit Reports。

## 验收标准

- Alerts 页面不是简单列表，必须展示运行上下文、统计摘要、活跃预警卡、反证/确认规则、事件窗口。
- 每条 alert 至少能跳转 Evidence 和 Run Logs。
- 反证/确认规则能跳转 Invalidation。
- 页面不出现原始 Python dict 样式条件。
- 页面继续使用 `text()`，API 中的历史 mojibake 文案能被前端修复。
- `npm run build` 通过。
- `python scripts/validate_p5_dashboard_contract.py` 通过。
- `python scripts/validate_p5_page_dod.py` 通过。

## 完成记录

- Alerts 页已升级为 `Alerts Workbench`：包含顶部预警摘要、统计卡、run lineage、活跃预警列表、反证/确认条件、事件窗口和操作入口。
- 每条 alert 已支持跳转 Evidence、Invalidation、Run Logs。
- 反证/确认条件已渲染为可读表达式，不显示 Python dict。
- 页面继续通过 `text()` 修复上游历史 mojibake 文案。
- 页面保持 FastAPI 聚合接口作为唯一数据源，不读取 SQLite，不解析 HTML 报告。

## 验收结果

- `npm run build` 通过。
- `python scripts/validate_p5_dashboard_contract.py` 通过。
- `python scripts/validate_p5_page_dod.py` 通过。
