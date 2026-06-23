# P11-C14 / FastAPI Lifespan Migration 与 Startup Contract Cleanup

## 状态

DONE

## Execution Record

### 2026-06-23 / Done

- 将 `backend/src/onlybtc/api/app.py` 从 `@app.on_event("startup")` 迁移到 FastAPI lifespan：
  - 新增 `app_lifespan` async context manager。
  - `FastAPI(title="onlyBTC API", version="0.1.0", lifespan=app_lifespan)`。
  - lifespan startup 继续调用 `_start_daemon_bootstrap_thread()`。
- 保持 runtime daemon bootstrap contract 不变：
  - thread name: `onlybtc-api-daemon-bootstrap`
  - daemon: `True`
  - starter 调用仍为 `auto=True`
  - 单个 starter 失败时继续后续 starter。
- 更新 `backend/tests/test_api_startup.py`：
  - 覆盖 lifespan context 触发 bootstrap thread。
  - 保留 starter failure continuation 测试。

Verification:

```powershell
.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\api\app.py backend\tests\test_api_startup.py
All checks passed

.\.venv\Scripts\python.exe -m pytest backend\tests\test_api_startup.py backend\tests\test_settings_contract.py backend\tests\test_glassnode_entitlement.py -q
10 passed

powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
passed: ruff, 8 pytest, backend audit, frontend build, npm audit
```

Notes:

- Focused pytest 不再输出 FastAPI `on_event` deprecation warning。
- 未修改 API response shape、策略逻辑、SQLite schema、full chain 或前端 UI。

## Summary

P11-C13 升级 FastAPI 后，测试与 smoke 仍出现 `@app.on_event("startup")` deprecation warning。本卡将 API startup hook 迁移到 FastAPI lifespan，保持 runtime daemon bootstrap contract 不变，并清理 CI 输出中的生命周期弃用警告。

## Scope

- `backend/src/onlybtc/api/app.py`
- `backend/tests/test_api_startup.py`
- 任务索引与本任务卡状态回填。

Out of scope:

- 不改变 Event Watchtower / Radar Runtime daemon 的启动顺序与 `auto=True` 契约。
- 不修改 API response shape。
- 不修改策略、数据采集、SQLite schema、full chain 或前端 UI。

## Business Chain / Contract

- Upstream: FastAPI application lifespan startup。
- Runtime contract: API 应用 lifespan 启动时创建 `onlybtc-api-daemon-bootstrap` daemon thread，线程内部依次调用 `event_watchtower_daemon.start(auto=True)` 与 `radar_runtime_daemon.start(auto=True)`。
- Error contract: 单个 daemon starter 失败时记录异常并继续启动后续 starter。
- Downstream: `/api/health`、settings contract、P45 dashboard、event window 与 radar runtime API response 不变。

## Implementation Plan

1. 引入 `asynccontextmanager` lifespan 函数。
2. 将 `FastAPI(..., lifespan=...)` 替代 `@app.on_event("startup")`。
3. 更新 startup 测试，覆盖 lifespan 触发 bootstrap thread 与 starter failure continuation。
4. 执行 focused pytest、ruff、smoke。
5. 通过后回填 DONE。

## DoD

- 不再使用 `@app.on_event("startup")`。
- focused pytest 不再输出 FastAPI `on_event` deprecation warning。
- daemon bootstrap thread name、daemon flag、`auto=True` 行为不变。
- `settings_contract` 与 `glassnode_entitlement` 测试继续通过。
- `fresh_clone_smoke.ps1 -SkipInstall` 通过。

## Test Plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_api_startup.py backend\tests\test_settings_contract.py backend\tests\test_glassnode_entitlement.py -q
.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\api\app.py backend\tests\test_api_startup.py
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
```

## Risks / Notes

- FastAPI/Starlette lifespan 只在应用生命周期启动时执行；现有非 context manager `TestClient(app)` 测试不会额外触发 daemon bootstrap，本卡保持测试环境行为稳定。
