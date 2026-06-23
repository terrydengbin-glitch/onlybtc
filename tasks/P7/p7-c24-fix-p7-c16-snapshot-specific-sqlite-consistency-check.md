# P7-C24 Fix P7-C16 Snapshot-specific SQLite Consistency Check

## 背景

P7-C23 全面审计发现：`event-window-state-overlay-llm-audit-report.html` 的 SQLite 一致性检查存在竞态。

当前审计脚本会读取 SQLite latest snapshot 并与本轮 audit payload 对比；但 Event Watchtower daemon 是常驻写入的，审计生成过程中 daemon 可能已经写入更新 snapshot，导致 `sqlite_latest_mismatch` 假失败。

## 目标

把 P7-C16 的 SQLite consistency check 从 `latest` 对比改为 `snapshot_id` 精确对比，使 HTML 2 审计在 daemon 常驻运行时也能稳定判断同源 payload。

## 范围

- `scripts/generate_event_window_state_overlay_llm_audit_html.py`
- `scripts/run_event_window_audit_bundle.py`
- 如有必要，补充 event window repository 的 `get_by_snapshot_id` 查询方法

## 核心要求

1. 审计脚本必须优先使用输入 payload 的 `snapshot_id` 查询 SQLite。
2. `sqlite_consistency` 输出必须标明 `comparison_mode = by_snapshot_id`。
3. 如果找不到对应 snapshot，才输出明确的 `snapshot_id_not_found`，不能退回 latest 后误判。
4. daemon 可以继续运行，审计不得因为后续新 snapshot 写入而失败。
5. HTML 1/2/3 bundle 必须继续显示同一个 `snapshot_id` 和 `asof_ts`。

## DoD

1. `scripts/run_event_window_audit_bundle.py` 只调用一次 collect once，并生成 HTML 1/2/3。
2. HTML 2 的 SQLite check 使用 `snapshot_id` 精确查询。
3. daemon 常驻运行时，bundle 不再出现 `sqlite_latest_mismatch` 假失败。
4. P7-C23 复审中该项从 `FAIL` 降为 `PASS` 或 `WARN`。
5. 任意 HTML 的 `snapshot_id` 不一致时，bundle summary 仍必须 FAIL。

