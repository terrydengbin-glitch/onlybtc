# P11-C17 / pip-audit AV False Positive Hardening

## 状态

DONE

## Execution Record

### 2026-06-23 / Done

- 调查安全日志命中路径：
  - `.venv/Lib/site-packages/cyclonedx/model/__pycache__/vulnerability.cpython-312.pyc`
- 确认来源：
  - `pip-audit 2.10.1`
  - `cyclonedx-python-lib 11.11.0`
  - 源文件 `cyclonedx/model/vulnerability.py` 是 CycloneDX vulnerability model。
- 校验结果：
  - 源文件 hash 与 wheel `RECORD` 匹配。
  - 源文件未发现 `subprocess`、`socket`、`eval`、`exec`、download 等执行型可疑代码。
- 缓解实现：
  - smoke 设置 `PYTHONDONTWRITEBYTECODE=1`。
  - backend audit 改为 `python -B -m pip_audit --skip-editable`。
  - smoke 在 audit 前清理特定 `cyclonedx/model/__pycache__/vulnerability*.pyc`。
  - CI backend audit 同步改为 `python -B -m pip_audit --skip-editable`。
  - README 手动命令同步为 `python -B -m pip_audit --skip-editable`。

Verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
passed: ruff, 8 pytest, backend audit, frontend build, npm audit

.\.venv\Scripts\python.exe -B -m pip_audit --skip-editable
No known vulnerabilities found

Get-ChildItem .\.venv\Lib\site-packages\cyclonedx\model\__pycache__ -Filter vulnerability*.pyc
no output
```

Notes:

- 这是 AV false-positive hardening，不是关闭安全检查。
- 如果安全软件未来继续拦截 `pip-audit` 进程行为，可考虑把 backend dependency audit 改为 CI-only 或使用隔离 audit venv。

## Summary

P11-C13 引入 `pip-audit` 后，本机安全日志报告 `HEUR:HackTool/VulnScan.a`，命中路径为 `.venv/Lib/site-packages/cyclonedx/model/__pycache__/vulnerability.cpython-312.pyc`。调查确认该文件来自 `pip-audit` 依赖 `cyclonedx-python-lib` 的漏洞数据模型 bytecode cache，源文件 hash 与 wheel RECORD 匹配，且未发现执行型可疑代码。本卡保留 Python dependency audit，但降低本机杀毒对 `vulnerability.pyc` 的启发式误报概率。

## Scope

- `scripts/fresh_clone_smoke.ps1`
- `.github/workflows/ci.yml`
- `README.md`
- `task index.md`
- 本任务卡。

Out of scope:

- 不移除 `pip-audit`。
- 不降低 dependency audit gate。
- 不添加杀毒软件白名单。
- 不修改策略、API response、SQLite schema、runtime daemon 或前端 UI。

## Business Chain / Contract

- Upstream: backend dev environment dependency audit。
- Security contract: `pip-audit --skip-editable` 仍必须执行并返回无已知漏洞。
- Local AV boundary: audit 运行使用 `python -B` / `PYTHONDONTWRITEBYTECODE=1`，并清理特定 CycloneDX vulnerability bytecode cache。
- CI contract: GitHub Actions 继续执行 backend audit，不生成不必要 bytecode。

## Implementation Plan

1. 将 backend audit invocation 改为 `python -B -m pip_audit --skip-editable`。
2. 在 smoke 中设置 `PYTHONDONTWRITEBYTECODE=1`。
3. 在 smoke audit 前清理特定 `cyclonedx/model/__pycache__/vulnerability*.pyc`。
4. 更新 README 的手动 audit 命令。
5. 执行 smoke、验证 `.pyc` 不再生成、回填 DONE。

## DoD

- `pip-audit` 仍执行并返回 no known vulnerabilities。
- smoke 通过。
- 本机 `cyclonedx/model/__pycache__/vulnerability*.pyc` 被清理且 audit 后不重建。
- CI 仍包含 backend dependency audit。

## Test Plan

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
Get-ChildItem .\.venv\Lib\site-packages\cyclonedx\model\__pycache__ -Filter vulnerability*.pyc
.\.venv\Scripts\python.exe -B -m pip_audit --skip-editable
```

## Risks / Notes

- 这是 AV 误报缓解，不是依赖安全降级。
- 如果安全软件仍拦截 `pip-audit` 行为本身，后续可把 audit 放到 CI-only 或隔离 venv 中执行。
