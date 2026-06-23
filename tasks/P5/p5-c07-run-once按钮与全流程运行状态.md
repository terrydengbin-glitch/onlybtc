# P5-C07 Run Once 按钮与全流程运行状态

## 状态

DONE

## 当前架构对齐（2026-05-22）

Run Once 必须触发 P4.5 主链路，而不是早期 mock run：

```text
p45-full-audit-with-llm --run-mode live --runtime-mode deterministic --llm-runtime-mode llm
```

FastAPI 入口：`POST /api/p45/run-full-with-llm`、`GET /api/p45/runs/latest`、`GET /api/runs/{run_id}`。

运行状态需要展示 P1/P2/P3/P4.5/LLM 子阶段，以及 LLM `completed_with_llm_errors` 的非阻塞降级。

Dashboard 需要额外提供“审计报告”入口。该入口复用同一条全链条 pipeline 生成的 P1/P2/P3/P4.5 HTML 报告，只作为人类审计查看，不作为前端数据源解析。

## UI / 高保真对齐（2026-05-22）

Run Once 与 Audit Reports 必须对齐高保真 Top Bar：

- `Run Full Chain` 主按钮位于 Top Bar 右侧。
- `Audit Reports` 以可点击 pill/link 展示，打开本轮审计报告索引。
- 点击 `Run Full Chain` 后打开 Run Logs 抽屉或跳转日志页，展示 P1/P2/P3/P4.5/LLM 阶段。
- 运行中 Top Bar 显示当前阶段；失败时显示失败阶段并提供 Run Logs 入口。
- 不允许按钮文案挤压或在移动端溢出。

## 所属 Phase

P5

## 任务目标

实现 Run Once 入口与全流程状态展示，让用户从 UI 触发 P1/P2/P3/P4 全链条并看到各阶段产物。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- Run Once 阶段至少包含：P1 collect、P1 HTML、P2 Radar、P2 HTML、P3 audit、P3 HTML、P4.5 evidence pack、P4.5 deterministic final、P4.5 LLM appendix、P4.5 HTML/API refresh。
- 展示每个阶段的 run_id、状态、耗时、失败原因、产物链接。
- Dashboard 顶部或 Run Once 区域提供 `Audit Reports` 按钮，点击打开本轮报告索引。
- 报告索引至少包含：P1 数据审计 HTML、P2 Radar 质检 HTML、P3 Algorithm Audit HTML、P4.5 Research Report HTML。
- 报告链接必须带本轮 run lineage，避免用户误打开旧 run 报告。
- 前端不得解析 HTML 报告作为数据源；HTML 只作为审计产物链接。
- 支持 SSE/WebSocket 进度订阅。
- 遵守 evidence + data、历史窗口、数据质量、反证机制和预警边界。
- 不输出交易建议，不引入开仓、止损、仓位或杠杆逻辑。

## 输入

- P9-C07 `POST /api/p45/run-full-with-llm`
- P9-C07 `GET /api/runs/{run_id}`
- P9-C07 `GET /api/p45/runs/latest`
- P9-C07 `GET /api/p45/audit-reports/latest`
- P9-C07 `GET /api/runs/{run_id}/audit-reports`
- P9-C10 实时推送

## 输出

- 可运行或可复用的代码、配置、Schema、接口、组件或文档。
- 必要的测试、验证记录或运行说明。

## 验收标准

- 与《开发文档.md》的总体架构一致。
- 用户能看到本轮是否生成 P1/P2/P3/P4.5 HTML、P4.5 final payload 和 LLM appendix。
- 用户能从 Dashboard 的 `Audit Reports` 按钮打开 P1/P2/P3/P4.5 原始审计报告。
- Run Full Chain 按钮必须调用 `POST /api/p45/run-full-with-llm`，不允许调用旧 mock run。
- Run Logs 展示 `completed_with_llm_errors` 为非阻塞降级，而非全链路失败。
- Playwright 验收必须覆盖 run idle/running/completed/failed 四种 UI 状态。
- 关键状态、错误和数据质量可观测。
- 不绕过 P4.5 final_view、反证/确认规则、预警等级或数据质量约束。

## 完成记录（2026-05-22）

- Top Bar `Run Full Chain` 继续调用 `POST /api/p45/run-full-with-llm`，并在点击后自动进入 Run Logs 页面。
- Top Bar 增加链路状态 pill，展示 `ready / running / failed / degraded` 与阶段数量。
- Run Logs 页面升级为阶段卡，展示 P1/P2/P3/P4.5/LLM 阶段的 run_id、status、非阻塞 LLM 降级说明和审计报告链接。
- 增加 Audit Reports 索引，展示 P1/P2/P3/P4.5 HTML 报告入口，报告仅作为审计产物打开，不作为前端数据源解析。
- FastAPI 增加只读 `/reports/` 静态报告入口；前端报告按钮优先打开 `/reports/<html>`，避免浏览器拦截 `file://`。
- 增加 `?page=logs` 页面初始化入口，方便验收和直接打开 Run Logs。
- 校验通过：`npm run build`、`python scripts/validate_p5_dashboard_contract.py`。
- 截图：`screenshots/p5-dashboard-c07-runlogs-page.png`。

## 依赖任务

P5-C15、P5-C20、P5-C25、P5-C26、P9-C07、P9-C10

## 备注

Run Once 的执行策略、权限和限流由 P9/P10 控制，P5 只提供触发入口和状态展示。
