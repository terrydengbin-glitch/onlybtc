# P7-C26 Event Window 审计 HTML 新鲜度门控与自动刷新修复

状态：DONE

## 背景

当前 Event Window 主业务链条仍在持续写入 SQLite，并且 `/api/event-window/latest` 已返回最新 snapshot：

```text
latest_snapshot_id = evt-20260529021701-4b3a05f7
latest_asof_ts     = 2026-05-29T02:17:01+00:00
```

但审计 HTML 1/2/3 仍停留在旧 snapshot：

```text
html_snapshot_id = evt-20260528124517-93f91e9e
html_asof_ts     = 2026-05-28T12:45:17+00:00
```

这说明：

```text
SQLite / API / daemon = live
audit HTML files      = stale
```

审计 HTML 是审计产物，不参与业务流；但它必须能明确反映当前链条是否最新，不能让用户误以为旧 HTML 就是当前状态。

## 目标

修复 Event Window 审计 HTML 的新鲜度问题，让 HTML 1/2/3 与 audit bundle summary 具备同源 snapshot 和 freshness gate。

最终链条：

```text
event daemon / run once
  -> SQLite latest snapshot
  -> audit bundle runner
  -> HTML 1/2/3
  -> bundle summary freshness gate
  -> PASS / STALE / FAIL
```

## 范围

涉及：

- `scripts/run_event_window_audit_bundle.py`
- `scripts/generate_event_window_source_audit_html.py`
- `scripts/generate_event_window_state_overlay_llm_audit_html.py`
- `scripts/generate_event_window_shock_fast_lane_audit_html.py`
- `reports/event-window-audit-bundle-summary.html`
- Event Window run once / audit bundle API 如已有挂载则补齐校验

不涉及：

- 不改变 Event Window daemon 采集逻辑
- 不改变 radar score
- 不让 UI 直接读取 HTML 文件作为业务数据

## 修复要求

1. audit bundle runner 必须先读取 SQLite latest snapshot。
2. HTML 1/2/3 必须基于同一个 `snapshot_id` 和 `asof_ts` 生成。
3. bundle summary 必须显示：
   - SQLite latest snapshot
   - source audit snapshot
   - state/overlay/LLM audit snapshot
   - shock fast lane audit snapshot
   - 各 HTML 文件 `LastWriteTime`
   - freshness verdict
4. 如果 HTML snapshot 与 SQLite latest snapshot 不一致：
   - bundle summary 标记 `STALE`
   - overall verdict 不允许 `PASS`
5. 如果 HTML 1/2/3 之间 snapshot 不一致：
   - bundle summary 标记 `FAIL`
6. 支持一键刷新：
   - 手动 run once 后可以立即生成 HTML 1/2/3
   - 或 audit bundle API 调用时自动重新生成 HTML 1/2/3
7. HTML 中必须展示 `generated_at`、`snapshot_id`、`asof_ts`，方便肉眼审计。
8. UI 只读取 API / SQLite 摘要状态，不直接消费 HTML 文件。

## DoD

1. 执行 audit bundle runner 后：

```text
reports/event-window-source-audit-report.html
reports/event-window-state-overlay-llm-audit-report.html
reports/event-window-shock-fast-lane-audit-report.html
reports/event-window-audit-bundle-summary.html
```

全部刷新。

2. HTML 1/2/3 与 bundle summary 的 `snapshot_id` 完全一致。
3. HTML 1/2/3 与 SQLite latest snapshot 的 `snapshot_id` 完全一致。
4. bundle summary 显示 `freshness_verdict = PASS`。
5. 若人为保留旧 HTML，不重新生成，bundle summary 能检测并显示 `STALE`。
6. `/api/event-window/latest` 最新 snapshot 与 bundle summary 对齐。
7. 增加至少一个测试或脚本级断言：

```text
html_snapshot_id == sqlite_latest_snapshot_id
```

8. 不影响 daemon health / watchdog / market probe 正常运行。

## 验收命令建议

```powershell
$env:PYTHONPATH='E:\onlyBTC\backend\src'
.\.venv\Scripts\python.exe scripts\run_event_window_audit_bundle.py
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower.py -q
```

## 备注

HTML 是审计镜像，不是业务数据源。业务实时状态以 SQLite + FastAPI 为准；HTML 必须通过 freshness gate 证明自己没有过期。
