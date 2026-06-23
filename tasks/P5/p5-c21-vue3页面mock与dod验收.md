# P5-C21 Vue3 页面 Mock 与 DoD 验收

## 状态

DONE

## 所属 Phase

P5 Dashboard 与可视化层

## 当前架构对齐

P5 页面层已经从 legacy P4 Debate 迁移到 P4.5 Report v2 契约：

- 上游数据来自 P1/P2/P3/P4.5 一键全链条 pipeline。
- 前端通过 FastAPI 聚合接口读取 Dashboard、Overview、Radar、Evidence、Article、Alerts、Invalidation、Data Quality、Run Logs、History、Settings。
- P1/P2/P3/P4.5 可审计 HTML 仍单独生成，并通过 FastAPI `/reports/` 静态路径打开。
- P4 legacy 信息仅作为内部参考，不参与 P4.5 `final_view`。

## 任务目标

建立页面级 DoD 验收脚本与清单，验证 P5 Vue3 页面在真实 API/fixture 数据下能稳定打开、跳转、展示降级状态，并保持同一 run lineage。

## 实施范围

- 覆盖 Dashboard、BTC Overview、Article、Evidence、LLM Appendix、Alerts、Invalidation、Data Quality、Run Logs、Source Detail、Radar Detail、History Replay、Settings。
- 验证 P4.5 Report v2 核心字段：`final_view`、`decision_card`、`aggregation_audit`、`horizon_views`、`contract_validation`、`publish_article`、`research_article`、`llm_research`、`llm_analyst_articles`。
- 验证 Radar module detail、Evidence detail、Source detail、History Replay、Audit Reports 均通过 FastAPI。
- 验证审计 HTML 按钮打开 `/reports/*.html`，不回到 Dashboard 首页。
- 验证 `publish_article` 不泄露 raw evidence id、run id、schema_version、Python dict。

## 输出

- 新增页面级自动验收脚本：[validate_p5_page_dod.py](../../scripts/validate_p5_page_dod.py)
- 新增 P5 页面 DoD 清单：[p5-page-dod-checklist.md](../ui/p5-page-dod-checklist.md)

## 验收命令

```powershell
npm run build
.\.venv\Scripts\python.exe scripts\validate_p5_dashboard_contract.py
.\.venv\Scripts\python.exe scripts\validate_p5_page_dod.py
```

## 验收结果

- `npm run build` passed。
- `scripts/validate_p5_dashboard_contract.py` passed。
- `scripts/validate_p5_page_dod.py` passed。
- 页面级 DoD 覆盖 `topology, overview, radar, evidence, article, alerts, invalidation, quality, source, conflict, logs, history, settings`。

## DoD

- 12+ 页面入口均可通过 `?page=` 独立打开。
- 所有页面继承或显示同一 run context。
- Radar chip、Evidence chip、Source chip 能跳转并加载对应 API。
- History Replay 能按 `final_run_id` 读取冻结 payload。
- Run Logs 展示 P1/P2/P3/P4.5/LLM stages 和审计报告链接。
- P1/P2/P3/P4.5 审计 HTML 通过 FastAPI 静态路径可达。
- fallback、stale、business recency、LLM runtime failure、confidence cap 具备可读展示入口。

## 备注

该任务完成后，P5 页面层可以继续逐页做像素级还原和子页面细化；每个页面改动后应继续运行本任务的两个校验脚本。
