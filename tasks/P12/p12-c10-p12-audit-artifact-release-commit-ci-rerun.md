# P12-C10 / P12 Audit Artifact Release Commit 与 CI Rerun

## 状态

TODO

## Summary

P12-C07 release acceptance 当前为 PARTIAL PASS，原因是 P12 审计产物仍在本地工作树中，远端 CI green baseline 尚未覆盖这些新报告和 runner。该任务负责提交 P12 审计产物、推送 GitHub，并确认新一轮 CI 成功。

## Scope

- P12 reports。
- `scripts/run_p12_system_audit.py`。
- P12 task cards and task index。
- GitHub Actions latest run。

Out of scope:

- 不修复 C08/C09 的业务 warning。

## Business Chain / Contract

- Release acceptance requires clean git working tree、CI green、smoke green、P12 reports present。
- C08/C09 warning 可以作为 known follow-up，但不能伪装为 fully clean release。

## Implementation Plan

1. 复跑 P12 audit runner 与 fresh clone smoke。
2. 提交并推送 P12 审计产物。
3. 检查 GitHub Actions 最新 run。
4. 更新 P12-C07 release acceptance 中 git/CI 证据。

## DoD

- Git 工作树干净。
- GitHub Actions latest run success。
- P12-C07 可从 PARTIAL PASS 中移除 git artifact warning；C08/C09 仍作为 known warnings。

## Test Plan

```powershell
.\.venv\Scripts\python.exe scripts\run_p12_system_audit.py
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
git status -sb
```

## Risks / Notes

- 若 GitHub Actions 排队或网络失败，记录 run URL 与当前 pending 状态。
