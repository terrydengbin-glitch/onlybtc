# onlyBTC

BTC trend sensing and alert system.

Current stage: P11 release hygiene and runtime hardening.

## Fresh Clone Smoke

The project is designed so a clean checkout can run the contract smoke without
local data, logs, cache, or real provider secrets.

```powershell
git clone https://github.com/terrydengbin-glitch/onlybtc.git
cd onlybtc
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1
```

For an existing local workspace with dependencies already installed:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
```

The smoke gate runs:

- Backend editable install when needed.
- Ruff on the current release contract files.
- Pytest for settings contract and Glassnode entitlement gates.
- Python dependency audit with `pip-audit`.
- Frontend `npm run build`.
- Frontend high severity audit with `npm audit --audit-level=high`.

GitHub Actions runs the same release gate on push, pull request, and manual
workflow dispatch.

## Backend

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .\backend[dev]
.\.venv\Scripts\python -m playwright install chromium
.\.venv\Scripts\python -m onlybtc.cli health
.\.venv\Scripts\python -m onlybtc.cli db-init
.\.venv\Scripts\python -m onlybtc.cli db-seed
.\.venv\Scripts\python -m onlybtc.cli db-health
.\.venv\Scripts\python -m onlybtc.cli collect-sources --mode mock
.\.venv\Scripts\python -m onlybtc.cli sources-health
.\.venv\Scripts\python -m onlybtc.cli metric-window btc_price
.\.venv\Scripts\python -m onlybtc.cli run-once
.\.venv\Scripts\python -m onlybtc.cli serve
```

Focused backend verification:

```powershell
.\.venv\Scripts\python -m pytest backend\tests\test_settings_contract.py backend\tests\test_glassnode_entitlement.py -q
.\.venv\Scripts\python -m ruff check backend\src\onlybtc\core\settings_contract.py backend\src\onlybtc\core\glassnode_entitlement.py backend\tests\test_settings_contract.py backend\tests\test_glassnode_entitlement.py scripts\generate_glassnode_entitlement_report.py
.\.venv\Scripts\python -B -m pip_audit --skip-editable
```

## Frontend

```powershell
cd frontend
npm ci
npm run dev
```

Build verification:

```powershell
npm run build
```

Default dev ports:

- Backend API: `http://127.0.0.1:8118`
- Frontend: `http://127.0.0.1:5188`

SQLite lives at `data/onlybtc.sqlite3` by default. Override it with `ONLYBTC_DATA_DIR`.

Live FRED collection requires `ONLYBTC_FRED_API_KEY`.

## Local Secrets And Data

- Keep `.env`, `data/`, `logs/`, `cache/`, local SQLite files, and build outputs out of git.
- Use `.env.example` as the documented template for local keys.
- CI intentionally does not require live provider keys; provider-specific checks run in dry-run or contract mode unless a later task explicitly adds a secret-backed workflow.
