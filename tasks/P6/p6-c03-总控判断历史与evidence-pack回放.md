# P6-C03 总控判断历史与 Evidence Pack 回放

## 状态

DONE

## 所属 Phase

P6 文章生成、历史记录与回测评分

## 任务目标

在 P6 article snapshot 之上建立总控判断历史和 Evidence Pack 冻结回放能力。回放必须以 `article_snapshot_id` 为锚点，只读取当时的 P6 draft、P4.5 final payload 和 `pack_id` 对应的 Evidence Pack，不得使用最新 runtime 状态覆盖历史结论。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)
- P6-C01 自动文章生成流程
- P6-C02 手动文章生成与 Run Once 发文策略
- P8-C08 文章、快照、History Replay 与评分表
- P9-C09 History Replay 聚合 API 与历史模式

## 实施范围

- 新增 P6 article history list：
  - `GET /api/p6/articles/history`
- 新增 P6 article replay：
  - `GET /api/p6/articles/replay/{article_snapshot_id}`
- Replay response 必须包含：
  - `schema_version=p6.article_replay.v1`
  - `history_mode.read_only=true`
  - `history_mode.historical_payload_frozen=true`
  - `history_mode.uses_latest_runtime_state=false`
  - P6 article snapshot
  - P4.5 final payload
  - Evidence Pack payload
  - citation vs pack evidence audit
  - run lineage
- History list response 必须包含：
  - `schema_version=p6.article_history.v1`
  - `history_mode.anchor=article_snapshot_id`
- 遵守 evidence + data、历史窗口、数据质量、反证机制和预警边界。
- 不输出交易建议，不引入开仓、止损、仓位或杠杆逻辑。

## 输入

- `p6.auto_article.v1`
- `p45.research_report.v2`
- `p45.evidence_pack.v1`
- SQLite `module_json_outputs`

## 输出

- P6 history/replay query functions
- FastAPI P6 history/replay endpoints
- Evidence Pack citation replay summary
- focused tests and regression verification

## 验收标准

- [x] `GET /api/p6/articles/history` 返回最近 P6 article snapshots，且 history mode 明确只读。
- [x] `GET /api/p6/articles/replay/{article_snapshot_id}` 可按 snapshot id 回放。
- [x] Replay 使用 snapshot 内的 `final_run_id` 和 `pack_id` 精确读取历史 payload，不读取最新 final 覆盖旧数据。
- [x] Evidence Pack replay 输出 pack evidence 总数、文章引用数、缺失引用和未引用证据数量。
- [x] Missing snapshot 返回标准 404 error envelope。
- [x] 不改变 P4.5 final 判断，不触发发布，不输出交易建议。

## 实施记录

2026-06-23：

- 扩展 `onlybtc.p6.article_pipeline`：
  - `P6_ARTICLE_HISTORY_SCHEMA_VERSION = p6.article_history.v1`
  - `P6_ARTICLE_REPLAY_SCHEMA_VERSION = p6.article_replay.v1`
  - `article_history(limit=50)`
  - `replay_article_snapshot(article_snapshot_id)`
- Replay 以 `article_snapshot_id` 为锚点，按 snapshot 内的 `final_run_id` 和 `pack_id` 精确读取：
  - P6 article snapshot
  - P4.5 final payload
  - P4.5 Evidence Pack payload
- 新增 Evidence Pack citation replay summary：
  - `pack_evidence_count`
  - `citation_count`
  - `unique_cited_evidence_count`
  - `missing_citation_count`
  - `uncited_evidence_count`
  - `traceability_status`
- 新增 FastAPI endpoints：
  - `GET /api/p6/articles/history`
  - `GET /api/p6/articles/replay/{article_snapshot_id}`
- 路由顺序已固定：`history` 与 `replay` 位于 `/{article_snapshot_id}` 之前，避免动态路由吞掉静态路径。

## 验证

- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m pytest backend\tests\test_p6_article_pipeline.py -q` -> 7 passed。
- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m pytest backend\tests\test_p6_article_pipeline.py backend\tests\test_p9_fastapi_page_contract.py backend\tests\test_api_security.py -q` -> 13 passed。
- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\p6 backend\src\onlybtc\api\app.py backend\tests\test_p6_article_pipeline.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\p6 backend\src\onlybtc\api\app.py backend\tests\test_p6_article_pipeline.py --select I,F` -> passed。

## 依赖任务

P6-C01、P6-C02、P8-C08、P9-C09

## 备注

P6-C03 只做历史与回放可观测层。预警历史、结果追踪、模块有效性评分留给 P6-C04 至 P6-C06。
