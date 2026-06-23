# P11-C13 / Backend Dependency 与 Python Toolchain Security Baseline

## 状态

DONE

## Execution Record

### 2026-06-23 / Done

- 初始 `pip-audit --skip-editable` 发现 7 个已知漏洞，集中在 2 个包：
  - `pydantic-settings 2.14.1` -> fixed by `2.14.2`
  - `starlette 1.0.0` -> fixed by `1.3.1`
- 将 backend dependency lower bounds 收紧：
  - `fastapi>=0.138.0`
  - `pydantic-settings>=2.14.2`
  - `starlette>=1.3.1`
- 将 `pip-audit>=2.10.1` 加入 backend dev dependencies。
- 在 `.github/workflows/ci.yml` backend job 加入：
  - `python -m pip_audit --skip-editable`
- 在 `scripts/fresh_clone_smoke.ps1` 加入：
  - `Audit backend dependencies`
- 更新 `README.md` 的 smoke / focused backend verification 说明。

Verification:

```powershell
.\.venv\Scripts\python.exe -m pip_audit --skip-editable
No known vulnerabilities found

.\.venv\Scripts\python.exe -m pytest backend\tests\test_settings_contract.py backend\tests\test_glassnode_entitlement.py -q
8 passed

powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
passed: ruff, 8 pytest, backend audit, frontend build, npm audit
```

Notes:

- FastAPI 升级到 `0.138.0` 后现有 `@app.on_event("startup")` deprecation warning 仍存在，但不阻塞本安全基线；后续可开专门 lifespan migration 卡。

## Summary

P11-C11/P11-C12 已把 GitHub CI、fresh clone smoke 与前端 high severity audit 纳入 release gate。本卡补齐 Python 后端依赖安全基线，使用 `pip-audit` 审计已安装 backend dev environment，确保 FastAPI、SQLAlchemy、Playwright、Pydantic、Uvicorn 等后端运行依赖没有已知漏洞继续进入 release gate。

## Scope

- `.github/workflows/ci.yml`
- `scripts/fresh_clone_smoke.ps1`
- 可选新增后端依赖审计脚本。
- 任务索引与本任务卡状态回填。

Out of scope:

- 不修改策略、评分、P1-P4.5 pipeline、SQLite schema 或 API response shape。
- 不引入真实 provider key。
- 不做 Python 大版本升级。
- 不把审计工具作为 runtime dependency。

## Business Chain / Contract

- Upstream: Python 3.12、backend editable install、dev dependencies、PyPI vulnerability database。
- Backend contract: 依赖安全审计只检查 install environment，不改变 `run_id`、`final_run_id`、`pack_id`、source freshness、settings contract、provider entitlement contract。
- Runtime/data boundary: 使用临时 `ONLYBTC_DATA_DIR`，不读取本地 `data/`、`.env`、logs、cache。
- CI contract: backend release gate 包含 Python dependency audit。

## Implementation Plan

1. 安装/调用 `pip-audit`，审计当前 backend dev environment。
2. 若发现漏洞，优先在兼容范围内最小升级依赖；若为工具自身依赖，隔离处理。
3. 将 Python dependency audit 纳入 CI 与 fresh clone smoke。
4. 执行 audit、backend focused tests、smoke。
5. 通过后回填 DONE。

## DoD

- Python dependency audit 通过。
- CI backend/fresh clone smoke 包含 Python dependency audit。
- settings contract 与 Glassnode entitlement pytest 通过。
- frontend build 与 npm high audit gate 不回退。
- 不改变业务策略与 runtime 数据契约。

## Test Plan

```powershell
.\.venv\Scripts\python.exe -m pip_audit
.\.venv\Scripts\python.exe -m pytest backend\tests\test_settings_contract.py backend\tests\test_glassnode_entitlement.py -q
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
```

## Risks / Notes

- `pip-audit` 依赖 PyPI advisory 数据，网络或远端服务异常可能造成 CI 波动；后续可引入 scheduled audit 或 SARIF 报告。
- 本卡先做 high-confidence installed environment audit，不做完整 SBOM/reproducible lock 方案。
