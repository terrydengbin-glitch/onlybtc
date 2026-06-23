# P1-C58 / Event Window v3 预期、Nowcast 与 FedWatch Live Snapshot

## 状态

DONE

## Phase

P1 数据源接入与采集层

## 当前断点

当前 `_expectation_snapshot()` 使用硬编码值：

```text
PCE consensus = 0.20
PCE nowcast = 0.25
CPI nowcast = 0.35
source_quality = embedded_fallback_until_live_connector
```

因此页面上的 expectation gap 是占位计算，不是 live consensus / nowcast / market-implied 数据。

## 目标

为 critical/high 事件维护真实预期快照：

```text
consensus:
  Trading Economics / configurable provider / manual override file

nowcast:
  Cleveland Fed CPI/PCE nowcast

market implied:
  CME FedWatch 或 Fed funds futures proxy

market drift:
  2Y yield
  10Y yield
  DXY
  Nasdaq / NDX
```

## 输出契约

```json
{
  "snapshot_id": "",
  "event_id": "",
  "snapshot_ts": "",
  "consensus": null,
  "previous": null,
  "forecast": null,
  "nowcast": null,
  "market_implied": null,
  "expectation_gap": null,
  "expectation_drift_1d": null,
  "expectation_drift_3d": null,
  "rate_cut_prob_drift_1d": null,
  "risk_direction": "hawkish|dovish|mixed|neutral|unknown",
  "source_quality": "live|partial|fallback|missing",
  "source_lineage": [],
  "data_quality_flags": []
}
```

## 实现要求

- 新增 `backend/src/onlybtc/event_window/connectors/expectations.py`。
- 支持 provider key 缺失时的显式 `consensus_missing`，不能伪造 consensus。
- Cleveland Fed nowcast 只可用于 CPI/PCE 风险提示，不能替代 actual。
- FedWatch / futures proxy 只输出 policy repricing，不直接输出 BTC 方向。
- 预期漂移从 SQLite 历史快照计算：

```text
expectation_drift_1d = current_consensus - consensus_1d_ago
expectation_drift_3d = current_consensus - consensus_3d_ago
rate_cut_prob_drift_1d = current_rate_cut_prob - rate_cut_prob_1d_ago
```

## 采样频率

由 daemon 根据 active event phase 自动切换：

```text
normal: 1h-6h
T-7d: 1h
T-24h: 10m-15m
event_lock: market-implied / rates / DXY 30s-60s
```

## DoD

- [x] live provider 可用时 `source_quality=live|partial`。
- [x] provider 不可用时输出 `consensus_missing` 或 `provider_unavailable`，不再静默 fallback。
- [x] T-7d 后可形成多条 expectation snapshot。
- [x] 能从历史快照计算 1d / 3d drift。
- [x] `/api/event-window/events/{event_id}/expectations` 返回历史快照。
- [x] run once 后 expectation connector 状态通过 source fetch / data quality flags 显式暴露。
- [x] 单元测试覆盖 provider success / missing key / drift / fallback flags。

## 实施记录（2026-06-23 状态回填）

- 实现入口已存在：
  - `backend/src/onlybtc/event_window/connectors/expectations.py`
  - `backend/src/onlybtc/event_window/connectors/atlanta_mpt.py`
  - `backend/src/onlybtc/event_window/connectors/prediction_markets.py`
  - `backend/src/onlybtc/event_window/provider_confidence.py`
  - `GET /api/event-window/events/{event_id}/expectations`
- 后续任务 P1-C63、P1-C64、P1-C67、P1-C68 已覆盖 consensus config、FedWatch proxy、prediction market odds 与 Atlanta MPT。
- 本次仅做任务状态回填，不修改运行代码。

## 验证记录

- `backend/tests/test_event_watchtower.py` 覆盖 expectation/source quality 相关路径。
- Event Watchtower API 已暴露 expectation history 查询。

## 依赖

- P1-C57
- P8-C35
- P9-C40
- P7-C15
