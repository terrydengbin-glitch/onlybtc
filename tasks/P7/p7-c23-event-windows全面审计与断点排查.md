项目启动
  -> event daemon auto start
  -> 分频 scheduler tick
  -> manual event run once
  -> official / secondary / proxy providers
  -> source lineage
  -> SQLite snapshot
  -> state machine
  -> emergency overlay
  -> shock fast lane
  -> market probe
  -> LLM speech analyzer
  -> HTML 1/2/3 audit bundle
  -> FastAPI endpoints
  -> Vue Event Watchtower page
  -> floating alert / muted icon / critical overlay
```

审计最终必须回答：

1. daemon 是否真实常驻运行，而不是只在 run once 时生成静态 JSON。
2. 数据源是否真实 live / fallback / proxy / missing，不能伪装 official live。
3. Scheduler 分频是否按事件临近程度和源类型执行。
4. SQLite 是否保存足够历史，UI 是否通过 FastAPI 读 SQLite / latest snapshot。
5. HTML 1/2/3 是否来自同一个 snapshot_id，而不是三份独立时刻的拼接。
6. Shock Fast Lane 是否能覆盖非日历突发和 BTC 市场暴跌。
7. Overlay 是否只改变交易权限 / radar trust / confidence cap，不直接改 BTC score。
8. LLM 是否只做语义解释，不直接给 BTC 多空或修改分数。
9. UI 是否显示真实 payload，而不是 mock 或 audit HTML 反向读取。

## 审计链条

### 1. 启动与 daemon 审计

检查：

- 项目启动时 Event Watchtower daemon 是否自动启动。
- daemon 与主 radar run once 是否互不阻塞。
- daemon status 是否包含：
  - runtime_version
  - daemon_enabled
  - daemon_running
  - heartbeat_ts
  - last_tick_ts
  - last_full_sweep_ts
  - stale_reason
  - next_due_sources
- daemon stale 时 UI 是否明确显示 stale，而不是继续显示旧 high / critical。

判定：

```text
heartbeat stale > threshold => daemon_stale
daemon_stale => UI warning + source diagnostics warning
daemon_stale 不允许伪装成 live
```

### 2. 分频 scheduler 审计

检查 scheduler 是否按源类型 / 事件阶段分频：

- 官方日历：低频，按天或小时刷新。
- Nowcast / expectation：T-7d 后加速，T-24h 后更高频。
- Actual polling：发布窗口前后高频。
- Fed RSS / official text：高频但限流。
- Shock Fast Lane：最高频，行情与快讯分开。
- Market probe：常驻独立，不能依赖 radar 主链。

审计要输出：

```json
{
  "source": "",
  "cadence_sec": 0,
  "last_run_ts": "",
  "next_due_ts": "",
  "is_due": false,
  "reason": "",
  "phase": "normal|t_minus_7d|t_minus_24h|event_lock|post_event|shock"
}
```

### 3. 数据源与 lineage 审计

检查每类源的状态：

- official_live
- official_html
- official_api
- official_mirror
- secondary_consensus
- prediction_market
- market_implied_proxy
- private_nowcast_proxy
- missing
- blocked

必须确认：

- BLS / BEA / Fed / FRED / Cleveland / FXStreet / Myfxbook / ForexFactory / Investing / Kalshi / Polymarket / Binance market probe 的 source_tier 正确。
- 403 / timeout / parse_error 被记录为 provider_failed，不静默降级。
- consensus missing 时不计算 actual-vs-consensus surprise。
- FedWatch proxy 不伪装成 CME FedWatch official probability。

### 4. SQLite 持久化与 replay 审计

检查：

- latest snapshot 是否入 SQLite。
- source fetch lineage 是否入 SQLite。
- market probe 多窗口数据是否入 SQLite。
- LLM analyses 是否入 SQLite 或 payload snapshot。
- timeline 是否按 timestamp 可回放。
- `/history` replay 是否能拿到历史 snapshot。

必须验证：

```text
UI -> FastAPI -> SQLite/latest snapshot
HTML -> audit output only
HTML 不参与业务数据回读
```

### 5. State Machine 与 Overlay 审计

检查状态优先级：

```text
data_quality_blocked
> unscheduled_shock_confirmed
> market_shock_confirmed
> event_lock
> release_surprise
> policy_repricing_shock
> fed_tone_shift
> pre_event_high_alert
> expectation_drift_watch
> calendar_monitor
> event_neutral
```

检查 overlay：

- `none`
- `reduce_size`
- `watch_only`
- `avoid_new_position`
- `event_lock`

硬规则：

```text
overlay.direct_score_impact 必须为 false
overlay 不能直接修改 BTC score / radar score
overlay 只能修改 trade_permission_modifier / confidence_cap / ordinary_radar_trust
```

### 6. Shock Fast Lane 审计

检查：

- 非日历官方突发
- 可信新闻多源确认
- exchange / stablecoin / regulatory / geopolitical / crypto_native
- BTC 5m / 15m / 1h / 4h 多窗口 market shock
- OI / liquidation / realized vol / return_z
- DXY / 2Y / NDX cross-asset proxy

必须验证：

```text
5h 暴跌场景至少触发 market_shock_watch 或 market_shock_confirmed
market_probe_stale 时不允许宣称 market_stable
单一 rumor 不允许 critical
official / multi_source / market_dislocation 可升级 high/critical
```

### 7. Post-event Reaction 审计

检查：

- T+5m first impulse
- T+30m absorption check
- T+2h follow-through
- T+24h trend acceptance

必须验证：

```text
hot CPI != automatic bearish
dovish Fed != automatic bullish
需要 BTC reaction / absorption / followthrough 验证
```

### 8. LLM Fed Speech Analyzer 审计

检查 LLM 输出：

- provider
- status
- tone
- confidence
- relevance
- boundary_pass
- summary_cn
- reason_cn
- direct_score_impact=false

硬规则：

```text
LLM 只能分类 tone / relevance / confidence / source meaning
LLM 不能输出 BTC bullish/bearish score
LLM confidence < 0.7 不允许触发 fed_tone_shift
not_policy_relevant 不允许参与 overlay 升级
ambiguous / data_dependent 必须允许存在
```

### 9. FastAPI 契约审计

至少检查：

- `/api/event-window/latest`
- `/api/event-window/status`
- `/api/event-window/calendar`
- `/api/event-window/timeline`
- `/api/event-window/alerts`
- `/api/event-window/source-diagnostics`
- `/api/event-window/run-once`
- `/api/event-window/audit-bundle`
- `/api/event-window/history`
- `/api/event-window/shock-lane/latest`
- `/api/event-window/post-event-reaction`

每个 endpoint 需要检查：

```text
HTTP 200
schema_version
snapshot_id
asof_ts
source_lineage
data_quality
no mock marker
no stale-as-live
```

### 10. UI 审计

检查 Event Watchtower 子页面：

- Live
- Calendar
- Timeline
- Speeches
- Shock Lane
- History
- source diagnostics
- LLM Policy Read
- LLM Analysis Table
- BTC Reaction Check
- Calendar Mini
- Dashboard Summary Widget
- Run Event Once
- Generate Audit Bundle
- daemon toggle/status

检查浮窗：

- high 使用右下浮窗。
- critical / event_lock 使用居中弹窗。
- mute 15m 后保留小图标。
- 小图标可点击展开。
- 浮窗可移动，不遮挡主操作。
- UI 文案说明 Event Window 不直接改 BTC score。

### 11. HTML 1/2/3 Bundle 审计

检查：

- HTML 1: source audit
- HTML 2: state / overlay / LLM audit
- HTML 3: shock fast lane audit
- bundle summary

必须验证：

```text
HTML 1/2/3 使用同一个 snapshot_id
HTML 1/2/3 使用同一个 asof_ts
任一不一致 => FAIL
HTML 仅作为审计文件，不参与 UI 业务数据读取
```

## 输出物

新增报告：

```text
reports/p7-c23-event-windows-full-chain-audit.md
reports/p7-c23-event-windows-full-chain-audit.json
```

可选 HTML：

```text
reports/p7-c23-event-windows-full-chain-audit.html
```

报告必须包含：

- 总体结论：PASS / PARTIAL PASS / FAIL
- 断点列表
- 每个断点所属层级
- 是否阻断生产使用
- 修复建议
- 对应任务卡建议
- 关键 API 返回摘要
- SQLite snapshot 摘要
- UI 数据来源验证
- HTML 1/2/3 snapshot 一致性验证

## DoD

- [x] 运行一次 Event Window manual full sweep。
- [x] 生成 HTML 1/2/3 bundle，并校验 snapshot_id / asof_ts 一致。
- [x] 检查 daemon status、heartbeat、scheduler cadence、next_due_sources。
- [x] 检查 source lineage：official / fallback / proxy / missing 均正确打标。
- [x] 检查 SQLite latest/history/replay 能读到同一份 snapshot。
- [x] 检查 FastAPI 全部 Event Window endpoint 返回契约字段。
- [x] 检查 UI 不读取 HTML，不使用 mock 数据。
- [x] 检查 overlay 不直接影响 BTC score / radar score。
- [x] 检查 LLM 不直接输出 BTC 多空分数。
- [x] 检查 Shock Fast Lane 能识别多窗口市场冲击，且 market probe stale 不伪装 stable。
- [x] 检查 Calendar Mini 不再显示错误 `0.0h`。
- [x] 检查 floating alert / muted icon / critical overlay 行为符合预期。
- [x] 输出 `reports/p7-c23-event-windows-full-chain-audit.md`。
- [x] 输出机器可读 `reports/p7-c23-event-windows-full-chain-audit.json`。
- [x] 若存在断点，给出精确到文件 / endpoint / task 的修复建议。

## 审计结果

```text
PARTIAL PASS
```

输出：

- `reports/p7-c23-event-windows-full-chain-audit.md`
- `reports/p7-c23-event-windows-full-chain-audit.json`

主要断点：

1. P7-C16 state/overlay/LLM audit 在 daemon 常驻时使用 `latest_snapshot()`，存在 `sqlite_latest_mismatch` 竞态。
2. `/api/event-window/shock-lane/latest` 在 DB 有 shock row 时返回 raw shock item shape，和 `payload.shock_fast_lane` aggregate shape 不完全一致。
3. Source mesh 当前为 partial live，属于可接受但必须显式展示的状态。
4. 后端 `tests/test_event_watchtower.py` 在 `.venv` 下超时，需补离线 deterministic 测试。

## Pass 标准

```text
PASS:
  主业务链条、SQLite、API、UI、HTML bundle、daemon 均无阻断断点。

PARTIAL PASS:
  存在非阻断缺口，例如部分 secondary consensus missing，但 official/fallback/proxy 标识正确，系统不 fake live。

FAIL:
  daemon 未运行、UI 使用 mock、HTML snapshot 不一致、overlay 直接改 BTC score、shock lane 漏掉明显 market shock、或 stale 数据伪装 live。
```
