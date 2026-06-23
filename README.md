# onlyBTC

BTC trend sensing and alert system.

Current stage: P0 engineering foundation.

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

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Default dev ports:

- Backend API: `http://127.0.0.1:8118`
- Frontend: `http://127.0.0.1:5188`

SQLite lives at `data/onlybtc.sqlite3` by default. Override it with `ONLYBTC_DATA_DIR`.

Live FRED collection requires `ONLYBTC_FRED_API_KEY`.
