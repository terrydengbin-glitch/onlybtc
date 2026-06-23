# P7-C25 Event Watchtower Deterministic Offline Test Suite

## 背景

P7-C23 全面审计发现：系统 Python 缺少依赖可以通过 `.venv` 解决，但 `tests/test_event_watchtower.py` 在 `.venv` 中出现超时，疑似测试触发 live connector / 网络路径。

Event Watchtower 的核心业务逻辑必须有离线、确定性、快速的测试套件；真实网络连接测试应单独标记，不进入默认快测链路。

## 目标

建立 Event Watchtower 离线确定性测试套件，覆盖状态机、overlay、SQLite roundtrip、Shock Fast Lane 多窗口判定、LLM 边界与 API 契约，同时避免真实网络阻塞。

## 范围

- `backend/tests/`
- Event Watchtower provider 注入 / fake provider fixtures
- pytest marker / test config

## 核心要求

1. 默认测试不得访问真实网络。
2. official calendar、nowcast、source mesh、market probe、LLM analyzer 均使用 fake payload。
3. live connector 测试必须单独标记为 `live` 或 `network`，默认跳过。
4. 测试必须覆盖：
   - daemon heartbeat stale 判定
   - manual run once full sweep
   - state machine priority
   - emergency overlay 不改变 BTC score
   - LLM 只输出 tone/relevance/confidence，不输出 BTC 多空
   - shock fast lane 多窗口行情冲击
   - SQLite snapshot 写入和按 snapshot_id 读取
   - `/api/event-window/shock-lane/latest` normalize 契约

## DoD

1. 新增离线测试文件，例如 `backend/tests/test_event_watchtower_offline.py`。
2. `.venv\\Scripts\\python -m pytest backend/tests/test_event_watchtower_offline.py -q` 在 30 秒内完成。
3. 默认 test 命令不因 live provider 访问超时。
4. P7-C23 复审不再记录 “backend test timeout” 为阻断项。

