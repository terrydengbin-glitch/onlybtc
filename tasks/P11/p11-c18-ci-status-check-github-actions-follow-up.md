# P11-C18 / CI Status Check 与 GitHub Actions Follow-up

## 状态

DONE

## Execution Record

### 2026-06-23 / Done

- 初始远端核查发现 P11 release hardening 后的 3 次 push workflow 均为 failure：
  - `87cb55c` -> failure
  - `19b8194` -> failure
  - `3c4d40b` -> failure
- GitHub Actions run details:
  - latest failed run: `28020287020`
  - URL: `https://github.com/terrydengbin-glitch/onlybtc/actions/runs/28020287020`
  - status: `completed`
  - conclusion: `failure`
  - jobs: `0`
- Root cause:
  - workflow parse-time failure。
  - GitHub page annotation reported `.github/workflows/ci.yml` line 15:
    `Unrecognized named-value: 'runner'`
  - `ONLYBTC_DATA_DIR: ${{ runner.temp }}\onlybtc-data` was used in job-level `env`, where `runner` context is not available.
- Fix:
  - removed `ONLYBTC_DATA_DIR` from backend job-level env.
  - added `Configure backend CI data dir` step:
    - creates `$env:RUNNER_TEMP\onlybtc-data`
    - writes `ONLYBTC_DATA_DIR=...` to `$GITHUB_ENV`
- Verification after push:
  - commit: `40fdbce`
  - run: `28020554319`
  - URL: `https://github.com/terrydengbin-glitch/onlybtc/actions/runs/28020554319`
  - workflow conclusion: `success`
  - jobs:
    - `Backend contract gate`: success
    - `Frontend build gate`: success
    - `Fresh clone smoke`: success

Local verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
passed: ruff, 8 pytest, backend audit, frontend build, npm audit
```

## Summary

P11-C11 至 P11-C17 已建立 release hardening gate 并推送到 GitHub。本卡核查远端 GitHub Actions 是否按预期触发并通过，确认 release baseline 在 GitHub 侧稳定。如果 CI 失败，则记录失败 job 与后续修复任务边界。

## Scope

- GitHub Actions run status。
- 当前 `origin/main` 最新 commit。
- `task index.md` 与本任务卡回填。

Out of scope:

- 不修改策略、API response、SQLite schema、runtime daemon 或 UI。
- 不安装 `gh`。
- 不创建 PR；当前分支为 direct-push main。

## Business Chain / Contract

- Upstream: `origin/main` commit `3c4d40b`。
- CI contract: `.github/workflows/ci.yml` 应触发 backend contract gate、frontend build/audit gate、fresh clone smoke。
- Release contract: GitHub Actions 通过后，P11 release hardening baseline 可视为远端稳定。

## Implementation Plan

1. 确认本地 `main` 与 `origin/main` 对齐。
2. 查询 GitHub Actions runs。
3. 对最新 commit 的 workflow run 做 job 级状态核查。
4. 如成功，回填 DONE；如失败，记录失败 job 与 follow-up。

## DoD

- 明确记录最新 workflow run status/conclusion。
- 明确记录 commit sha。
- 如 CI 通过，本卡 DONE。
- 如 CI 未触发或失败，说明原因并给出下一步任务。

## Test Plan

```powershell
git status -sb
Invoke-RestMethod https://api.github.com/repos/terrydengbin-glitch/onlybtc/actions/runs
```

## Risks / Notes

- 当前环境未安装 `gh`，因此使用 GitHub REST API 查询公开 Actions 状态。
- 如果仓库或 Actions API 需要认证，需后续安装/auth `gh` 或配置 token。
