# P11-C15 / Release Commit Hygiene 与 GitHub Push

## 状态

DONE

## Execution Record

### 2026-06-23 / Done

- 确认当前分支：`main`，远端：`origin https://github.com/terrydengbin-glitch/onlybtc.git`。
- 当前环境未安装 `gh`，因此不创建 PR，仅按 direct git push 上传。
- 工作树存在与本卡无关的 runtime report 修改，已排除：
  - `reports/radar-runtime-audit-report.html`
  - `reports/radar-runtime-audit-report.md`
- 本次提交范围限定为 P11-C11 至 P11-C15 release hardening：
  - GitHub Actions CI。
  - fresh clone smoke。
  - frontend/backend dependency security gate。
  - FastAPI lifespan cleanup。
  - README 与任务卡回填。

Verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
passed: ruff, 8 pytest, backend audit, frontend build, npm audit
```

## Summary

P11-C11 到 P11-C14 已完成 release hygiene、前后端依赖安全基线与 FastAPI lifespan cleanup。本卡将这些变更整理为一次有边界的 Git commit 并推送到 GitHub，排除与本次 release hardening 无关的 runtime report 工作树修改。

## Scope

- P11-C11 至 P11-C15 任务卡与 `task index.md`。
- GitHub Actions CI workflow。
- Fresh clone smoke 脚本。
- README release verification 说明。
- backend/frontend 安全依赖与 lifespan cleanup 代码。
- Git staging、commit、push。

Out of scope:

- 不提交 `reports/radar-runtime-audit-report.html`。
- 不提交 `reports/radar-runtime-audit-report.md`。
- 不创建 PR；当前环境未安装 `gh`。
- 不修改策略、数据采集、full chain 输出或 runtime report 证据。

## Business Chain / Contract

- Upstream: local P11 release hardening changes。
- Git contract: 只 staging 白名单文件；混合工作树中 runtime report 修改保持未暂存。
- CI contract: push 后 GitHub Actions 应运行 backend contract gate、frontend build/audit gate、fresh clone smoke。
- Runtime/data boundary: 不提交 `.env`、`data/`、logs、cache、local SQLite 或 runtime report 修改。

## Implementation Plan

1. 确认工作树和远端。
2. 执行 fresh clone smoke。
3. 白名单 staging P11 release hardening 文件。
4. 检查 staged diff。
5. commit 并 push 到 `origin/main`。
6. 回填本卡 DONE。

## DoD

- Staged diff 不包含 runtime report 修改。
- Smoke 验证通过。
- Commit 创建成功。
- Push 到 GitHub 成功。
- 本卡和 `task index.md` 记录 commit / push 结果。

## Test Plan

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
git diff --cached --name-only
git push origin main
```

## Risks / Notes

- `gh` CLI 未安装，因此本卡只做 direct push，不开 draft PR。
- 如 push 后 GitHub Actions 失败，后续按 CI log 单独开卡修复。
