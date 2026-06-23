# P8-C34 / TimeScale Judge payload 持久化与 replay

## 状态

DONE

## 目标

确保 `btc_timescale_judge.v2.1` 随 P4.5 final payload 完整落盘，并支持 latest/history/replay 读取同一份历史快照。

## 范围

- 不新增业务表时，优先复用 final payload JSON 持久化。
- 如现有 replay 查询需要白名单字段，则补齐 `btc_timescale_judge`。
- 保证历史回放不会用当前 run 的 horizon judge 覆盖历史 run。

## DoD

1. 每次 P4.5 运行落盘完整 `btc_timescale_judge`。
2. latest 查询可读取最新 `btc_timescale_judge`。
3. history replay 可读取历史 run 对应 `btc_timescale_judge`。
4. run_id / final_run_id / generated_at 可追踪。
5. payload hash 或 lineage 可追踪 cockpit 输入变化。
6. SQLite/repository 单测覆盖缺字段兼容。

## 验收命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

## 关联任务

P4.5-C43, P9-C39, P5-C61

## 验收记录

- `btc_timescale_judge` 已进入 final payload。
- SQLite final payload 持久化验证通过。
- `history/{final_run_id}` 可读取历史对应 `btc_timescale_judge`。
