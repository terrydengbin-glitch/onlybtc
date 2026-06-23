# P5 页面 DoD 验收清单

## 范围

P5-C21 用于确认 Vue3 页面层已经能消费 P1/P2/P3/P4.5 的最新链路数据，并且页面、API、审计 HTML、历史回放保持同一套 run lineage。

## 页面清单

| 页面 | 入口 | 数据来源 | 验收点 |
| --- | --- | --- | --- |
| Dashboard 拓扑 | `?page=topology` | `/api/p45/dashboard/latest`、`/api/p45/radar-modules/latest` | BTC 决策卡、14 个 Radar 节点、动态连线、Run Full Chain、Audit Reports |
| BTC Overview | `?page=overview` | `/api/p45/overview/latest` | final_view、decision_card、horizon_views、why_not_strong |
| Radar Detail | `?page=radar` | `/api/p45/radar-modules/latest`、`/api/p45/radar-modules/{module_id}` | module score、metric evidence、freshness、duplicate、horizon |
| Evidence | `?page=evidence` | `/api/p45/evidence`、`/api/p45/evidence/{evidence_id}` | metric_score、metric_effective_score、source、freshness、brief |
| Article | `?page=article` | `/api/p45/articles/latest` | publish_article、research_article、LLM Research Appendix、四分析师 LLM |
| Alerts | `?page=alerts` | `/api/p3/alerts/latest`、`/api/p3/events/latest`、`/api/p45/invalidation/latest` | alerts、cooldown、事件窗口、halving、反证/确认摘要 |
| Invalidation | `?page=invalidation` | `/api/p45/invalidation/latest` | invalidation_rules、confirmation_rules |
| Data Quality | `?page=quality` | `/api/data-quality/latest` | data_quality、contract、missing freshness、source health |
| Source Detail | `?page=source` | `/api/sources/{source_id}` | source、runs、metrics、fallback/stale/business recency 线索 |
| Conflict | `?page=conflict` | `/api/p45/evidence` | duplicate_group_id 与多源重复影响 |
| Run Logs | `?page=logs` | `/api/p45/runs/latest`、`/api/p45/audit-reports/latest` | P1/P2/P3/P4.5/LLM stages、审计 HTML 按钮、Run Full Chain 状态 |
| History Replay | `?page=history` | `/api/p45/history/{final_run_id}` | 冻结 final payload、退出历史模式、不污染 latest |
| Settings | `?page=settings` | `/api/settings` | provider、model、timeout、运行默认值 |

## 必须覆盖的降级场景

| 场景 | 页面表现 |
| --- | --- |
| `contract_validation.status=passed_with_warning` | Dashboard 与 Data Quality 显示 warning，不空白 |
| unavailable metric freshness warning | Data Quality 和 Evidence 显示边界，不阻塞主视图 |
| LLM completed | Article 展示 LLM Research Appendix 与四分析师摘要 |
| LLM completed_with_llm_errors | Run Logs 标记为非阻塞降级，final_view 不被 LLM 附录覆盖 |
| data quality degraded | BTC 节点出现质量提示，Data Quality 可读 |
| historical replay | History Replay 进入冻结上下文，latest refresh 不覆盖 |
| legacy P4 reference | 仅作为 legacy/internal reference，不参与 P4.5 final_view |

## 自动验收命令

```powershell
npm run build
.\.venv\Scripts\python.exe scripts\validate_p5_dashboard_contract.py
.\.venv\Scripts\python.exe scripts\validate_p5_page_dod.py
```

## DoD

- 12+ 页面入口都可以通过 `?page=` 独立打开。
- Dashboard、Overview、Article、Radar、Evidence、Alerts、Quality、Run Logs、History、Settings 全部从 FastAPI 读取数据。
- P1/P2/P3/P4.5 审计 HTML 通过 FastAPI `/reports/` 静态路径打开，不回到 Dashboard 首页。
- Radar chip、Evidence chip、Source chip、History Replay 均能走对应 API。
- `publish_article` 不泄露 raw evidence id、run id、schema_version、Python dict。
- 页面级脚本与 Dashboard 契约脚本全部通过。
