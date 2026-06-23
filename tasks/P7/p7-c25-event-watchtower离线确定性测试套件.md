# P7-C25 / Event Watchtower 离线确定性测试套件

## 背景

P7-C23 审计发现当前后端测试存在两个问题：

1. 系统 Python 环境缺 `sqlalchemy`，需要明确测试运行环境。
2. `.venv` 下运行 `tests/test_event_watchtower.py` 超时，疑似测试会触发 live connector / network / daemon 线程。

Event Window 是关键风险层，必须有不依赖外网、不依赖长时间 daemon 的确定性测试。

## 目标

新增离线 deterministic test suite，覆盖核心业务边界：

- 状态机优先级
- overlay score isolation
- LLM boundary
- shock fast lane 多窗口判定
- SQLite roundtrip
- audit snapshot 固定化

## 修改范围

- `backend/tests/test_event_watchtower_offline.py`
- 必要时给 connectors 增加 fixture/mock 输入。
- CI / 本地文档中明确使用：

```powershell
$env:PYTHONPATH='E:\onlyBTC\backend\src'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_event_watchtower_offline.py -q
```

## 测试原则

```text
不访问外网
不启动真实 scheduler loop
不调用 DeepSeek API
不依赖当前时间，使用固定 datetime
不写生产 SQLite，使用 tmp sqlite
```

## DoD

- [ ] 新增离线测试文件。
- [ ] 测试能在 30 秒内完成。
- [ ] 覆盖 sustained_5h_crash_regression。
- [ ] 覆盖 no-shock normal-noise。
- [ ] 覆盖 critical shock override。
- [ ] 覆盖 LLM 不直接输出 BTC score。
- [ ] 覆盖 overlay 不包含 `btc_score / radar_score / module_score`。
- [ ] 覆盖 audit snapshot by id，不依赖 latest。

