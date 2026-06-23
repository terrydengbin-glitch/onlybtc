# P11-C12 / Frontend Dependency Security Audit 与 Lockfile Hygiene

## 状态

DONE

## Execution Record

### 2026-06-23 / Done

- 确认 `npm audit --json` 仅报告 1 个 high severity item：
  - package: `vite`
  - affected range: `<=6.4.2`
  - advisories: Windows UNC / fs deny bypass related Vite advisories。
- 将前端 dev dependency `vite` 从 `^6.3.5` 升级到 `^6.4.3`，并同步更新 `frontend/package-lock.json`。
- 在 `.github/workflows/ci.yml` frontend job 加入：
  - `npm audit --audit-level=high`
- 在 `scripts/fresh_clone_smoke.ps1` 加入：
  - `Audit frontend dependencies`

Verification:

```powershell
npm audit --audit-level=high
found 0 vulnerabilities

npm run build
passed with vite v6.4.3

powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
passed: ruff, 8 pytest, frontend build, npm audit
```

## Summary

P11-C11 本地 smoke 过程中发现 `npm audit` 存在 1 个 high severity vulnerability，直接依赖为 `vite <=6.4.2`。本卡做最小前端依赖安全修复与锁文件治理，把 high severity audit 纳入 release gate，避免后续 CI/fresh clone 继续携带已知高危依赖。

## Scope

- `frontend/package.json`
- `frontend/package-lock.json`
- `.github/workflows/ci.yml`
- `scripts/fresh_clone_smoke.ps1`
- 任务索引与本任务卡状态回填

Out of scope:

- 不升级 Vue 主版本。
- 不修改前端业务组件、API contract 或页面交互。
- 不处理 backend Python 依赖安全审计。
- 不使用 `npm audit fix --force`。

## Business Chain / Contract

- Upstream: npm registry、`package-lock.json`、GitHub Actions Node 20。
- Frontend contract: TypeScript compile + Vite production build。
- Runtime boundary: 仅影响 dev/build toolchain，不改变 `/api/*` response shape、BTC card、radar runtime、SQLite 数据或 full chain 输出。
- CI contract: high severity audit 必须为 0；moderate/low 先作为后续治理，不阻塞本卡。

## Implementation Plan

1. 确认 `npm audit --json` 漏洞来源与可修复范围。
2. 将 Vite 在 6.x 内升级到修复版本。
3. 在 CI frontend job 与 fresh clone smoke 中加入 `npm audit --audit-level=high`。
4. 本地执行 audit、build、smoke。
5. 通过后回填 DONE。

## DoD

- `npm audit --audit-level=high` 通过。
- `npm run build` 通过。
- `powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall` 通过。
- CI/smoke release gate 包含 high severity npm audit。
- 不引入前端源码行为变更。

## Test Plan

```powershell
npm audit --audit-level=high
npm run build
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
```

## Risks / Notes

- Vite 升级限定在 6.x patch/minor 范围，降低构建行为变化风险。
- 若 npm registry 出现新的 high advisory，本卡 gate 会正确失败，后续按新的审计结果继续修。
