# P6-C07 文章回放评分 Mock 与 DoD 验收

## 状态

DONE

## 所属 Phase

P6 文章生成、历史记录与回测评分

## 任务目标

用 mock 总控结果和历史快照验证文章生成、历史回放、24h/72h/7D 结果跟踪与评分闭环。P6-C07 未通过，不进入 P7。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)
- P6-C01 至 P6-C06
- P8-C08 文章、快照、History Replay 与评分表
- P9-C12 FastAPI 集成测试与页面契约验收

## 实施范围

- 验证自动文章与手动 Run Once 文章生成。
- 验证文章引用 evidence_id，不输出无法追溯的结论。
- 验证历史 snapshot 冻结，不读取当前实时状态。
- 验证 24h/72h/7D 结果跟踪与评分。
- 验证模块有效性、误报率、领先时间、噪音评分。
- 新增 P6 DoD API：
  - `POST /api/p6/dod/mock-run`
  - `GET /api/p6/dod/latest`
- DoD runner 输出：
  - `schema_version=p6.dod_report.v1`
  - `status=passed|warning|failed`
  - `checks[]`
  - `replay_scores_written`
  - `calibration_notes_written`
  - `report_paths`
- DoD runner 可写入 `replay_scores` 与 `calibration_notes`，但必须标记只读校准建议，不允许生产权重 mutation。

## 输入

P6-C01 至 P6-C06，P4-C11 mock final JSON，P8-C08。

## 输出

- article mock fixtures。
- replay mock fixtures。
- scoring mock report。
- P6 DoD 验收清单。
- reports/p6-dod-report.json
- reports/p6-dod-report.md

## 验收标准

- 文章可由同一 snapshot 重复生成且结果稳定。
- Article 页面能展示证据引用、模型摘要、风险提示。
- History Replay 能回放当时状态并计算后续表现。
- 回测评分可写入 `replay_scores` 和 `calibration_notes`。
- P6 DoD 全部通过后，才允许进入 P7。
- DoD API 不输出交易建议，不修改 P4.5 final，不修改模块权重。

## 实施记录

2026-06-23：

- 新增 `onlybtc.p6.dod`：
  - `P6_DOD_REPORT_SCHEMA_VERSION = p6.dod_report.v1`
  - `run_p6_dod_mock(article_snapshot_id=None, run_mode=live, write_scores=true)`
  - `latest_p6_dod_report()`
- 新增 FastAPI endpoints：
  - `POST /api/p6/dod/mock-run`
  - `GET /api/p6/dod/latest`
- DoD runner 聚合：
  - P6 article history
  - P6 article replay
  - P6 alert quality
  - P6 outcome tracking
  - P6 module effectiveness
- DoD runner 幂等写入：
  - `replay_scores`
  - `calibration_notes`
- 报告落盘：
  - `reports/p6-dod-report.json`
  - `reports/p6-dod-report.md`
- 边界固定：
  - `production_weight_mutation=false`
  - `mutates_final_view=false`
  - `trading_advice=false`

## 验证

- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m pytest backend\tests\test_p6_dod.py -q` -> 2 passed。
- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m pytest backend\tests\test_p6_article_pipeline.py backend\tests\test_p6_alert_quality.py backend\tests\test_p6_outcome_tracking.py backend\tests\test_p6_module_effectiveness.py backend\tests\test_p6_dod.py backend\tests\test_p9_fastapi_page_contract.py backend\tests\test_api_security.py -q` -> 24 passed。
- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\p6 backend\src\onlybtc\api\app.py backend\tests\test_p6_dod.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\p6 backend\src\onlybtc\api\app.py backend\tests\test_p6_dod.py --select I,F` -> passed。
- Online smoke：
  - `POST /api/p6/dod/mock-run?write_scores=true` -> `schema_version=p6.dod_report.v1`，`status=warning`，9 checks，`trading_advice=false`，`production_weight_mutation=false`。
  - `GET /api/p6/dod/latest` -> returns latest `p6.dod_report.v1`。
  - reports generated:
    - `/reports/p6-dod-report.json`
    - `/reports/p6-dod-report.md`

## 实施记录

TBD

## 验证

TBD

## 依赖任务

P6-C01、P6-C02、P6-C03、P6-C04、P6-C05、P6-C06

## 备注

文章是系统解释层，不是交易指令；生成结果必须保留不确定性和反证条件。
