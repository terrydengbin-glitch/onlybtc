# P5-C62 / Post Event Reaction Validator

## 状态

DONE

## Execution Record

### 2026-06-23 / Start

- 用户要求继续，P1-C61/P1-C62 已完成后接入 P5-C62。
- 当前缺口：`post_event_reaction` 只有 BTC return 与 absorbed/followthrough/fakeout，缺 `reaction_state`、realized vol、OI/funding/CVD/OFI proxy 与 UI 解锁提示。
- 约束：不允许 simple rule `hot CPI = bearish`；reaction 只描述事件后 BTC 行为，不直接改 radar / BTC score。

### 2026-06-23 / Completion

- Added `reaction_state`, `realized_volatility`, `oi_change`, `funding_rate`, `basis`, `cvd_proxy`, `ofi_proxy`, `event_lock_release_allowed`, and `event_lock_release_reason`.
- Kept surprise calculation gated by `actual_status=available` and consensus availability.
- Fixed SQLite naive datetime handling for T+5m / T+30m / T+2h return windows by interpreting stored timestamps as UTC.
- Added deterministic tests for pending, absorbed, followthrough, and actual-status surprise gating.
- Updated frontend BTC Reaction Check to display post-event reaction fields and event-lock release state.
- Audit report: `reports/p5-c62-post-event-reaction-validator-audit.md`.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower.py -k "post_event_reaction or reaction_requires" -q
.\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\event_window\connectors\reactions.py backend\tests\test_event_watchtower.py
npm run build
```

Result:

- P5-C62 focused tests: 4 passed.
- Compile check: passed.
- Frontend build: passed.

## Phase

P5 Dashboard 与可视化层 / 事件后反应验证

## 背景

宏观事件的专业判断不能停在 “CPI 热 = bearish” 或 “Fed dovish = bullish”。Event Window v3 必须验证 BTC 是否吸收冲击、假突破、延续冲击或进入 event lock 后恢复普通 radar 可信度。

## 目标

在事件发布后记录并展示：

```text
T+5m BTC return
T+30m BTC return
T+2h BTC return
realized volatility
OI change
funding / basis
CVD / OFI / taker delta
shock_absorbed
followthrough
```

## 输出契约

```json
{
  "post_event_reaction": {
    "actual": null,
    "consensus": null,
    "surprise_raw": null,
    "surprise_z": null,
    "btc_return_5m": null,
    "btc_return_30m": null,
    "btc_return_2h": null,
    "btc_absorbed_shock": null,
    "followthrough": null,
    "reaction_state": "pending|first_impulse|absorbed|followthrough|fakeout|insufficient_data"
  }
}
```

## 判断规则

```text
hot CPI + BTC 5m down but 30m recovers most drawdown
=> shock_absorbed

hawkish Fed + BTC loses pre-event low and fails to reclaim in 30m/2h
=> policy_shock_followthrough

dovish surprise + BTC spikes but CVD weakens and OI falls
=> relief_rally_weak
```

## DoD

- [x] 记录 BTC return_5m / 30m / 2h。
- [x] 记录 OI、funding、CVD/OFI proxy、realized vol。
- [x] 输出 absorbed / followthrough / fakeout。
- [x] 不允许 simple rule：hot CPI = bearish。
- [x] UI 可以展示事件后反应是否允许解除 event lock。
- [x] 测试覆盖 pending、absorbed、followthrough 三类。

## 依赖

- P3-C56
- P8-C35
- P9-C40
- P5-C63
