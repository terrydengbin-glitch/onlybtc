# P11-C16 / Runtime Report Working Tree Policy

## 状态

DONE

## Execution Record

### 2026-06-23 / Done

- 确认 `reports/radar-runtime-audit-report.html` 与 `.md` diff 为 runtime latest snapshot 刷新：
  - `generated_at`
  - `runtime_snapshot_id`
  - `runtime_asof_ts`
  - source freshness gate
  - module score / contribution / accepted status
- 确认生成入口：
  - `onlybtc.radar_runtime.audit_report.generate_radar_runtime_audit_report()`
- 确认 API contract：
  - `p45_dashboard.audit_reports()` 在文件不存在时跳过，不阻塞 response。
  - runtime 生成后仍通过 `/reports/radar-runtime-audit-report.html` 暴露。
- 将以下 latest mutable runtime artifacts 加入 `.gitignore`：
  - `reports/radar-runtime-audit-report.html`
  - `reports/radar-runtime-audit-report.md`
- 使用 `git rm --cached` 从 Git index 移出上述两个文件，本地文件保留。

Verification:

```powershell
Test-Path reports\radar-runtime-audit-report.html
True

Test-Path reports\radar-runtime-audit-report.md
True

git check-ignore -v reports\radar-runtime-audit-report.html reports\radar-runtime-audit-report.md
matched .gitignore

powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
passed: ruff, 8 pytest, backend audit, frontend build, npm audit
```

Notes:

- 本卡只处理 runtime latest report。P7/P10 等任务验收静态报告仍保留追踪。
- 后续如果要保留可审计 runtime evidence，应输出 run_id/archive bundle，而不是覆盖 latest 文件。

## Summary

P11-C15 推送后，本地工作树仍反复出现 `reports/radar-runtime-audit-report.html` 与 `reports/radar-runtime-audit-report.md` 修改。这两个文件由 `onlybtc.radar_runtime.audit_report.generate_radar_runtime_audit_report()` 写入，内容包含 `generated_at`、`runtime_snapshot_id`、source freshness、模块分数和 health transition 等运行态 latest snapshot。继续纳入 Git 跟踪会让 daemon 正常刷新污染工作树。

## Scope

- `.gitignore`
- Git index 中 radar runtime latest report 的追踪状态。
- `task index.md`
- 本任务卡。

Out of scope:

- 不删除本地 `reports/radar-runtime-audit-report.html` / `.md` 文件。
- 不修改 report 生成逻辑、API response shape、runtime daemon、SQLite schema 或前端 UI。
- 不改变 P7/P10 等静态审计报告是否追踪。

## Business Chain / Contract

- Upstream: Radar Runtime daemon / audit report generator。
- Runtime artifact: `reports/radar-runtime-audit-report.html` 与 `.md` 是 latest mutable artifacts，由 runtime 刷新。
- API/UI contract: `p45_dashboard.audit_reports()` 会在文件存在时返回 `/reports/radar-runtime-audit-report.html`；fresh clone 中文件缺失时跳过，不阻塞 API。
- Git contract: latest mutable runtime artifact 不进入版本控制；本地文件保留并被 `.gitignore` 忽略。

## Implementation Plan

1. 确认当前 diff 为 runtime timestamp/run_id/source freshness/scores 刷新。
2. 将 radar runtime latest report 路径加入 `.gitignore`。
3. 使用 `git rm --cached` 从 Git index 移出这两个文件，保留本地文件。
4. 验证 `git status` 不再显示它们的修改。
5. 运行 focused smoke。
6. 回填 DONE。

## DoD

- 两个 runtime latest report 不再污染工作树。
- 本地 report 文件仍存在，可被 FastAPI `/reports/*` 静态挂载访问。
- `p45_dashboard.audit_reports()` 文件缺失跳过的 contract 保持不变。
- fresh clone smoke 通过。

## Test Plan

```powershell
Test-Path reports\radar-runtime-audit-report.html
Test-Path reports\radar-runtime-audit-report.md
git status --short
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
```

## Risks / Notes

- 这次只处理 runtime latest report。其他 P7/P10 静态审计报告仍作为任务验收证据保留在版本库中。
- 若未来需要可复现的 radar runtime evidence，应写入带 run_id 的 archive/report bundle，而不是覆盖 latest 文件。
