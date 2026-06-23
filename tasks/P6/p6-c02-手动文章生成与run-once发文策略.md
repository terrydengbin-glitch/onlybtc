# P6-C02 手动文章生成与 Run Once 发文策略

## 状态

DONE

## 所属 Phase

P6 文章生成、历史记录与回测评分

## 任务目标

在 P6-C01 自动 draft snapshot 的基础上，提供手动生成与查询 API，并固化 Run Once 后的发文策略：Run Once / Full Chain 可自动生成 draft，但不得自动发布；发布必须进入后续人工确认和渠道策略任务。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)
- P6-C01 自动文章生成流程
- P9-C11 API 权限、审计、限流与脱敏

## 实施范围

- 新增手动生成 API：
  - `POST /api/p6/articles/generate`
- 新增查询 API：
  - `GET /api/p6/articles/latest`
  - `GET /api/p6/articles/{article_snapshot_id}`
- API 返回 `p6.manual_article.v1` envelope。
- 明确 Run Once 发文策略：
  - `run_once_auto_generates_draft=true`
  - `auto_publish_allowed=false`
  - `manual_review_required=true`
  - `publication_status=draft_only`
- 保留 P9-C11 写操作审计；手动生成 endpoint 会进入 `audit_logs`。
- 不输出交易建议，不引入开仓、止损、仓位或杠杆逻辑。

## 输入

- `p6.auto_article.v1`
- P4.5 final payload：`p45.research_report.v2`
- API audit middleware

## 输出

- P6 article API endpoints
- 手动生成 envelope
- Run Once publication strategy object
- focused tests

## 验收标准

- [x] `POST /api/p6/articles/generate` 可按 `final_run_id` 生成或返回幂等 draft。
- [x] `GET /api/p6/articles/latest` 可返回最近 draft。
- [x] `GET /api/p6/articles/{article_snapshot_id}` 可按 snapshot id 查询。
- [x] response 明确 `publication_status=draft_only` 和 `auto_publish_allowed=false`。
- [x] 手动生成写操作进入 API audit。
- [x] 不改变 P4.5 final 判断，不触发任何真实发布。

## 执行记录（2026-06-23）

- 扩展 `onlybtc.p6.article_pipeline`：
  - `P6_MANUAL_ARTICLE_SCHEMA_VERSION = p6.manual_article.v1`
  - `manual_generate_article(final_run_id=None)`
  - `latest_manual_article()`
  - `get_manual_article(article_snapshot_id)`
- 新增 FastAPI endpoints：
  - `POST /api/p6/articles/generate`
  - `GET /api/p6/articles/latest`
  - `GET /api/p6/articles/{article_snapshot_id}`
- Manual response envelope 包含：
  - `article_snapshot_id`
  - `final_run_id`
  - `draft_status`
  - `publication_status=draft_only`
  - `article`
  - `run_once_publication_strategy`
- Run Once 发文策略已固化：
  - `run_once_auto_generates_draft=true`
  - `auto_publish_allowed=false`
  - `manual_review_required=true`
  - `publication_status=draft_only`
- P9-C11 middleware 自动记录 `POST /api/p6/articles/generate` 到 `audit_logs`。

## 验证

- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m pytest backend\tests\test_p6_article_pipeline.py -q` -> 5 passed。
- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m pytest backend\tests\test_p6_article_pipeline.py backend\tests\test_p9_fastapi_page_contract.py backend\tests\test_api_security.py -q` -> 11 passed。
- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\p6 backend\src\onlybtc\api\app.py backend\tests\test_p6_article_pipeline.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\p6 backend\src\onlybtc\api\app.py backend\tests\test_p6_article_pipeline.py --select I,F` -> passed。
- Online smoke：
  - `POST /api/p6/articles/generate` -> `schema_version=p6.manual_article.v1`，`publication_status=draft_only`，`auto_publish_allowed=false`。
  - `GET /api/p6/articles/latest` -> returns same latest snapshot。
  - `GET /api/p6/articles/not-found` -> standard P9 error envelope。
  - `GET /api/p45/runs/latest` -> `api_security.audit_logs` contains `/api/p6/articles/generate` success event。

## Notes

- 本卡不执行真实发布，不连接任何外部渠道。
- 手动生成是幂等 draft 准备动作；人工确认、渠道发布、撤回策略留给后续卡。

## 依赖任务

P6-C01、P9-C11、P9-C12

## 备注

本卡只完成生成/查询/策略边界。人工确认、渠道发布、外部推送留给后续任务。
