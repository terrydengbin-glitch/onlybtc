# P9-C57 API Startup Nonblocking Daemon Bootstrap

## 状态

DONE

## 所属 Phase

P9 前端集成与 API 契约

## 任务目标

修复 FastAPI startup 同步执行 Event Watchtower / Radar Runtime daemon 首轮采集导致 API 长时间停留在 `Waiting for application startup` 的问题。API 应先完成 listen，daemon 首轮采集继续在后台执行，避免前端 API 在启动期不可用。

## 背景依据

- [P9-C41](p9-c41-event-watchtower-daemon常驻运行与推送.md)
- [P9-C49](p9-c49-radar-runtime-daemon-scheduler-health-api.md)
- [P9-C54](p9-c54-radar-runtime-source-refresh-gate.md)
- [P7-C35](../P7/p7-c35-radar-runtime-source-gate-async-collect-bridge.md)

## 实施范围

- FastAPI startup event 改为启动后台 bootstrap thread。
- 后台 thread 顺序启动 Event Watchtower 和 Radar Runtime daemon。
- 保留现有 daemon `start(auto=True)` 契约、health/status API、scheduler thread 行为。
- 不修改 source collection、source freshness gate、SQLite schema、前端 DTO。

## 输入

- `onlybtc.api.app` FastAPI startup hook
- `event_watchtower_daemon.start(auto=True)`
- `radar_runtime_daemon.start(auto=True)`

## 输出

- API startup 不再被首轮 daemon/full sweep 阻塞。
- 后台 daemon bootstrap 有异常日志，不阻断 API listen。
- 单元测试覆盖 startup hook 只调度后台 thread，不同步执行 daemon start。

## 验收标准

- [x] `onlybtc.cli serve --port 8118` 能在短时间内进入 listen。
- [x] `/api/health` 返回 200。
- [x] startup 后台 thread 会调用两个 daemon 的 `start(auto=True)`。
- [x] daemon bootstrap 异常不会让 FastAPI startup 失败。
- [x] 不改变 Run Full Chain / manual tick / scheduler API 契约。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_api_startup.py backend\tests\test_api.py backend\tests\test_radar_runtime_daemon.py -q`
- 启动 `onlybtc.cli serve --host 127.0.0.1 --port 8118`，确认 8118 listen。
- `curl.exe -s http://127.0.0.1:8118/api/health`

## 验证结果

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_api_startup.py backend\tests\test_api.py backend\tests\test_radar_runtime_daemon.py -q` -> 18 passed.
- Restarted backend on `127.0.0.1:8118`; Uvicorn reached `Application startup complete` and listen state.
- `curl.exe -s http://127.0.0.1:8118/api/health` -> `status=healthy`.
- `curl.exe -s http://127.0.0.1:8118/api/event-window/latest` -> HTTP 200 response.
- Startup log scan found no `coroutine was never awaited`, `RuntimeWarning`, `Traceback`, or daemon bootstrap error.
- Radar Runtime daemon starts in background; immediately after API listen it may report `stale/no_scheduler_tick_yet` until the first background full sweep completes.

## 风险 / 回滚

- 风险：API 先 listen 后 daemon 首轮快照尚未完成，短时间内 health/status 可能显示 starting/not_started。处理方式：保留 daemon health/status 字段展示真实启动状态。
- 回滚：恢复 startup hook 直接同步调用两个 daemon 的 `start(auto=True)`。
