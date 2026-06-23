# P7-C24 / Event Window 审计 Snapshot 固定化修复

## 背景

P7-C23 全面审计发现：`P7-C16 Event Window 状态机、Overlay 与 LLM Analyzer 第二审计 HTML` 的核心业务边界都通过，但报告仍显示 FAIL，原因是：

```text
sqlite_latest_mismatch
```

根因不是状态机或 LLM 失败，而是审计脚本在 daemon 常驻运行时使用 `latest_snapshot()` 比对当前 payload。由于 Event Watchtower daemon 会继续 scheduler tick 并写入新 snapshot，审计过程中 SQLite latest 可能被推进，导致当前审计 payload 和 latest 不一致。

## 目标

让 Event Window 审计脚本基于固定 `snapshot_id` 审计，而不是依赖随时会变化的 `latest_snapshot()`。

## 修改范围

- `scripts/generate_event_window_state_overlay_llm_audit_html.py`
- 必要时扩展：
  - `EventWatchtowerRepository.get_snapshot(snapshot_id)`
  - `scripts/run_event_window_audit_bundle.py`

## 业务规则

```text
审计 bundle 一旦生成 payload，就固定 snapshot_id。
HTML 1 / 2 / 3 的所有 SQLite consistency 检查都必须以该 snapshot_id 为准。
daemon 可以继续运行，但不能影响本轮审计结论。
```

禁止：

- 用 `latest_snapshot()` 判断某个固定 payload 是否已持久化。
- 为了审计强行停止 daemon。
- 把 daemon 继续写入新 snapshot 误判为业务失败。

## 实现建议

1. 在 repository 中新增：

```python
def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None
```

2. `generate_event_window_state_overlay_llm_audit_html.py` 中：

```text
sqlite_consistency:
  query snapshot by payload.snapshot_id
  compare state / overlay / direct_score_impact
```

3. 报告中同时展示：

```text
audited_snapshot_id
current_latest_snapshot_id
latest_may_advance_due_to_daemon = true
```

## DoD

- [ ] P7-C16 HTML 不再因 daemon tick 产生 `sqlite_latest_mismatch`。
- [ ] P7-C16 报告显示 audited snapshot 与 current latest snapshot。
- [ ] P7-C21 bundle 继续保证 HTML 1/2/3 同一 `snapshot_id / asof_ts`。
- [ ] P7-C23 复跑时该断点关闭。
- [ ] 不需要停止 Event Watchtower daemon。

