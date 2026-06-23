# P11-C11 / GitHub CI、Fresh Clone Smoke 与 Release Hygiene

## 状态

DONE

## Execution Record

### 2026-06-23 / Done

- 新增 `.github/workflows/ci.yml`：
  - backend contract gate：Python 3.12、editable install、ruff、settings/glassnode pytest。
  - frontend build gate：Node 20、`npm ci`、`npm run build`。
  - fresh clone smoke：调用 `scripts/fresh_clone_smoke.ps1`。
- 新增 `scripts/fresh_clone_smoke.ps1`：
  - 使用临时 `ONLYBTC_DATA_DIR`。
  - 支持 fresh clone 默认安装与本机 `-SkipInstall` 快速验证。
  - 对 `pip`、`ruff`、`pytest`、`npm` 外部命令强制检查退出码，避免 PowerShell 误报成功。
  - 已存在 `node_modules` 时不执行破坏式 `npm ci`，避免本机 dev server / antivirus 锁定二进制时清空依赖；CI clean checkout 仍会执行 `npm ci`。
- 更新 `README.md`：
  - fresh clone smoke 指令。
  - focused backend verification。
  - frontend build verification。
  - 本地 secrets/data 与 CI 边界说明。

Verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
passed: ruff, 8 pytest, frontend build

npm run build
passed
```

Notes:

- 本地默认安装模式首次暴露 `npm ci` 被锁定的 `esbuild.exe` 中断问题，脚本已修复为严格退出码检查，并避免在已有 workspace 中默认清空 `node_modules`。
- `npm install` 修复本机前端依赖时提示 1 个 high severity audit item；本卡不升级前端依赖树，后续可开安全依赖审计任务。

## Summary

onlyBTC 已完成首次 GitHub 上传，需要把“本机可运行”升级成“fresh clone 可复现、push/PR 自动验证、敏感配置不进入仓库”的 release hygiene 基线。本卡聚焦 CI 与启动说明，不改变策略语义、评分参数、数据采集口径或交易判断。

## Scope

- GitHub Actions CI workflow。
- Fresh clone smoke 脚本。
- README 启动、测试、CI 与安全配置说明。
- 任务索引与本任务卡状态回填。

Out of scope:

- 不接入真实 provider key。
- 不跑 full chain 或 LLM 调用。
- 不修改 BTC 4H/1D Direct Trend 策略语义。
- 不处理 runtime DB retention；另开后续任务。

## Business Chain / Contract

- Upstream: GitHub checkout、Python 3.12、Node 20、`.env.example`、backend editable install、frontend dependencies。
- Backend contract: settings contract、provider entitlement dry-run/report contract、FastAPI import contract。
- Frontend contract: Vue3 TypeScript build contract。
- Runtime/data boundary: CI 使用临时 `ONLYBTC_DATA_DIR`，不读取本机 `data/`、`.env`、logs、cache。
- Secrets boundary: CI 不要求真实 API key；`.env` 与本地数据库保持 gitignored。

## Implementation Plan

1. 新增 `.github/workflows/ci.yml`。
2. 新增 `scripts/fresh_clone_smoke.ps1`，覆盖 backend install、关键测试、ruff gate、frontend install/build。
3. 更新 README，明确 fresh clone、CI、本地数据和密钥边界。
4. 本地执行 smoke 相关命令。
5. 通过后将本卡与 task index 标记为 DONE。

## DoD

- GitHub Actions 在 push / PR / manual dispatch 触发。
- CI backend job 通过 Python 3.12 安装、ruff gate、关键 pytest。
- CI frontend job 通过 Node 20 安装与 `npm run build`。
- Fresh clone smoke 脚本不依赖本机 `.env`、`data/`、logs 或 cache。
- README 能指导新机器启动、测试和理解 CI 范围。
- 本地验证通过。

## Test Plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_settings_contract.py backend\tests\test_glassnode_entitlement.py -q
.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\core\settings_contract.py backend\src\onlybtc\core\glassnode_entitlement.py backend\tests\test_settings_contract.py backend\tests\test_glassnode_entitlement.py scripts\generate_glassnode_entitlement_report.py
npm run build
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
```

## Risks / Notes

- 先采用窄 CI gate，避免历史任务里与本卡无关的宽量级测试或 live provider 行为阻塞上传后的基础回归。
- 后续可在 P11-C12 扩展为 full regression matrix、runtime API smoke、scheduled report publish。
