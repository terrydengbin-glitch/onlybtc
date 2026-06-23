# P9-C53 / Radar Runtime SQLite Lock + Source Freshness Gate

## 状态

DONE

## 背景

Radar Runtime 已经升级为常驻 daemon，并按模块 cadence 分频刷新 14 个 radar modules。但本轮审计发现主链 runtime 与 Event Window 的稳定性不一致：

```text
Event Window daemon:
  healthy，heartbeat / watchdog / source cadence 正常。

Radar Runtime daemon:
  degraded，last_tick_age 超过阈值；
  last_error = sqlite3.OperationalError: database is locked；
  next_due_modules = 14 个模块全部积压；
  radar-runtime-audit-report.html 未跟随异常刷新到最新状态。
```

同时还发现一个更深的业务断层：

```text
runtime module snapshot 显示 fresh，
但 module_payload.features 内部仍引用过期的 P1 fast source，
例如 binance-btcusdt-kline / open-interest / funding 已 expired 数百分钟。
```

这说明当前 health 只看 module snapshot age 不够，必须同时检查：

```text
runtime_fresh = module snapshot 是否按 cadence 更新
source_fresh  = module 使用的底层 P1 feature/source 是否仍在 freshness policy 内
```

## 目标

修复 Radar Runtime 常驻链条的写入锁、source freshness gate、异常审计刷新和 API/UI 表达，使主链达到与 Event Window 类似的常驻运行可靠性。

核心目标：

```text
1. SQLite 写入不再因并发 run once / daemon tick / audit persist 互相锁死。
2. Runtime health 同时暴露 runtime_fresh 与 source_fresh。
3. Fast module tick 前必须刷新或确认对应 P1 fast source。
4. 审计 HTML 在 daemon 异常或 stale 时即时刷新。
5. Dashboard/API/UI 明确区分“模块快照新鲜”和“底层数据新鲜”。
```

## 范围

涉及：

- P9 Radar Runtime daemon / scheduler / health API
- P8 SQLite session / WAL / busy timeout / retry / snapshot persistence
- P1 fast source freshness gate
- P7 Radar Runtime 审计 HTML 与全链路复审
- Vue3 runtime health 展示

不涉及：

- 重写 14 个 radar module 算法
- 取消 P4.5 acceptance / residual gate
- 让 Event Window 直接修改 BTC score
- 用 UI 颜色掩盖数据 stale

## 业务规则

### 1. SQLite 写入锁治理

所有 Radar Runtime 写入 SQLite 的路径必须使用统一写入保护：

```text
busy_timeout >= 10s
WAL enabled
短事务
写入 retry with backoff
单写锁 / async lock / process lock 至少覆盖 daemon tick 与 audit persist
```

如果写入仍失败：

```text
daemon health_state = degraded
last_error 保留完整错误摘要
审计 HTML 立即落盘
不允许 UI 显示 healthy
```

### 2. runtime_fresh 与 source_fresh 分离

Runtime module health 必须拆成两层：

```json
{
  "runtime_freshness": {
    "state": "fresh|stale|expired|missing",
    "age_sec": 0,
    "ttl_sec": 0
  },
  "source_freshness": {
    "state": "fresh|partial|stale|expired|missing",
    "stale_feature_count": 0,
    "expired_feature_count": 0,
    "blocking_feature_count": 0,
    "sample_stale_features": []
  },
  "effective_participation": "full|discounted|watch_only|blocked"
}
```

模块 snapshot fresh 但 source expired 时：

```text
module_freshness_state 不得简单显示 fresh；
effective_participation 至少降级为 discounted；
fast trigger 不允许升级 confirmed；
主 BTC runtime fast readout 必须标记 source stale / partial。
```

### 3. Fast module tick 前的 P1 source gate

fast cadence modules：

```text
kline_orderflow
trade_structure_flow
derivatives_crowding
asia_risk
```

在 tick 前必须确认或刷新对应 fast source：

```text
binance-btcusdt-kline-5m / 15m / 1h
binance-btcusdt-open-interest
binance-btcusdt-funding
binance agg/trade/orderflow proxy if available
asia session BTC response derived inputs
```

规则：

```text
source fresh:
  正常执行 module tick

source stale but refresh success:
  使用刷新后的 source 执行 module tick

source stale and refresh failed:
  module tick 可以生成 snapshot，但必须 source_fresh=false，参与降权

source expired and blocking:
  module contribution 不得参与 fast confirmed / bullish / bearish 强结论
```

### 4. 审计 HTML 异常即时刷新

`reports/radar-runtime-audit-report.html` 不只按固定周期刷新，还必须在以下情况立即刷新：

```text
daemon health_state != healthy
sqlite write error
all modules due / scheduler backlog
runtime snapshot stale
source_freshness degraded
fast source expired
```

HTML 必须显示：

```text
runtime snapshot age
daemon last_tick_age
last_error
SQLite lock/retry summary
runtime_fresh / source_fresh 双层矩阵
每个 module 的 stale/expired feature 样本
next_due_modules
最后一次 audit_html_generated_at
```

### 5. API / Dashboard 契约

以下 API 需要透传双层新鲜度：

```text
/api/radar-runtime/daemon/status
/api/radar-runtime/modules/latest
/api/radar-runtime/cockpit/latest
/api/p45/dashboard/latest
```

新增或标准化字段：

```json
{
  "runtime_health": {
    "runtime_fresh": true,
    "source_fresh": true,
    "source_freshness_state": "fresh|partial|stale|expired|missing",
    "sqlite_lock_state": "ok|retrying|degraded",
    "write_retry_count": 0
  }
}
```

### 6. UI 展示边界

前端必须区分：

```text
Runtime fresh:
  module snapshot 是否按频率更新

Source fresh:
  module 使用的数据是否还有效
```

当 source_fresh 不通过：

```text
主 BTC 卡 fast layer 显示 partial / stale
Radar detail 显示 source stale 样本
不允许只用绿色 fresh 误导用户
```

## DoD

- [ ] Radar Runtime daemon 不再因 SQLite `database is locked` 长时间进入 degraded。
- [ ] SQLite 写入路径有 busy timeout / retry / 单写保护。
- [ ] `/api/radar-runtime/daemon/status` 暴露 `runtime_fresh`、`source_fresh`、`sqlite_lock_state`。
- [ ] `/api/radar-runtime/modules/latest` 每个 module 暴露 runtime freshness 与 source freshness 双层状态。
- [ ] fast module snapshot fresh 但底层 source expired 时，module effective participation 被降级。
- [ ] fast module tick 前会刷新或确认对应 P1 fast source。
- [ ] `btc_runtime_cockpit` 聚合时会对 source stale module 降权。
- [ ] `radar-runtime-audit-report.html` 在异常时即时刷新，并显示 stale source 样本。
- [ ] Dashboard BTC 主卡能显示 runtime fresh + source fresh 两层状态。
- [ ] P4.5 confirmed 信号仍必须经过 acceptance/residual gate，不被 runtime 单点覆盖。
- [ ] 回归审计证明 14 个 module cadence 不积压，source freshness 不掉链子。
- [ ] 后端测试通过。
- [ ] `npm run build` 通过。

## 验收命令

```powershell
$env:PYTHONPATH='E:\onlyBTC\backend\src'

# 单元/集成测试
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radar_runtime_daemon.py backend\tests\test_sources.py -q

# 手动触发一次 runtime tick
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/run-once' -Method Post

# 检查 health
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/daemon/status' | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/modules/latest' | ConvertTo-Json -Depth 6
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/cockpit/latest' | ConvertTo-Json -Depth 6

# 审计 HTML
.\.venv\Scripts\python.exe scripts\generate_radar_runtime_audit_report.py

# 前端
cd frontend
npm run build
```

## 审计重点

人工复审时重点确认：

```text
1. daemon status 不再 degraded。
2. last_tick_age 持续低于阈值。
3. next_due_modules 不再长期为 14。
4. module snapshot fresh 时，底层 feature 不再大量 expired。
5. source_fresh=false 时，UI 和 cockpit 不会当作完整 fresh 使用。
6. radar-runtime-audit-report.html 的 LastWriteTime 与 daemon 最新异常/快照一致。
```
