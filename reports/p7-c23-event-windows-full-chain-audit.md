# P7-C23 / Event Windows 全面审计与断点排查复审

结论：**PASS**

本轮复审基于同一次 Event Watchtower manual full sweep 生成的 HTML 1/2/3 bundle，snapshot_id 为 `evt-20260528071743-ef1977ec`，asof 为 `2026-05-28T07:17:43.212652+00:00`。

## 修复闭环

| 项目 | 旧问题 | 复审结果 |
|---|---|---|
| P7-C24 | P7-C16 使用 SQLite latest 对比，daemon 写入时会假失败 | PASS：HTML 2 改为 `comparison_mode=by_snapshot_id` |
| P9-C47 | `/shock-lane/latest` 有 DB shock row 时返回 raw shape | PASS：接口稳定返回 aggregate contract，并携带 `latest_item` |
| P5-C82 | partial live / fallback / failed source 可见性不足 | PASS：Event Watchtower 和 Dashboard summary 暴露 source mode/count/disabled capabilities |
| P7-C25 | 后端测试可能触发 live connector 导致超时 | PASS：新增离线确定性测试，4 项用例 1.75s 通过 |

## 当前业务链条

| 环节 | 结果 | 证据 |
|---|---|---|
| 独立 daemon | PASS | `standalone_daemon`，scheduler enabled |
| Event Window run once | PASS | manual full sweep 与主链路 run once 隔离 |
| 分频 scheduler | PASS | source group cadence 仍由 daemon 维护 |
| SQLite 持久化 | PASS | snapshot、source fetch、market probe、shock、LLM analysis 均可落库 |
| FastAPI | PASS | `/latest`、`/shock-lane/latest`、`/audit-bundle/latest` 等可消费结构化 payload |
| Vue UI | PASS | UI 读取 FastAPI/store，不消费 HTML 文件 |
| HTML 1/2/3 审计 | PASS | bundle summary `overall_status=PASS` |
| Market shock regression | PASS | sustained crash / normal noise / sustained rally 三类通过 |
| Overlay 边界 | PASS | `direct_score_impact=false`，只改变交易权限和 radar trust |
| LLM 边界 | PASS | 只输出 tone / relevance / confidence / 中文解释，不直接给 BTC 多空 |

## 关键验证结果

### HTML Bundle

```text
overall_status: PASS
snapshot_id_consistent: true
asof_ts_consistent: true
state_overlay_llm_audit: PASS
shock_fast_lane_audit: PASS
market_shock_regression: PASS
```

### State / Overlay / LLM HTML 2

```text
SQLite consistency: true
comparison_mode: by_snapshot_id
sqlite_snapshot_id: evt-20260528071743-ef1977ec
payload_snapshot_id: evt-20260528071743-ef1977ec
```

### Shock Lane API

`/api/event-window/shock-lane/latest` 当前返回：

```text
shock_detected: true
shock_type: crypto_native
emergency_level: high
confirmation_level: market_dislocation
source_count: 1
summary: BTC 24h market dislocation
latest_item_from_sqlite: true
```

### 离线测试

```text
.venv\Scripts\python -m pytest backend/tests/test_event_watchtower_offline.py -q
4 passed in 1.75s
```

### 前端 Build

```text
npm run build
PASS
```

## 残余说明

Event Window 当前仍是 partial live，这是事实状态，不是阻断项。系统必须继续显示 live / partial / fallback / failed 与 disabled capabilities，不能把 proxy 或 fallback 伪装成 official live。

## 最终判断

P7-C23 复审通过。Event Windows 主链路、独立 daemon、SQLite、FastAPI、UI、HTML 审计、Shock Fast Lane、LLM 边界与离线测试均已闭环。

