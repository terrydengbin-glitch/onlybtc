# P9-C39 / TimeScale Judge API 透传

## 状态

DONE

## 目标

FastAPI 对 Dashboard / Overview / History 统一透传 `btc_timescale_judge.v2.1`，前端优先消费新契约，旧 `horizon_views` 保持 fallback。

## API 范围

- `/api/p45/dashboard/latest`
- `/api/p45/overview/latest`
- `/api/p45/history`
- 如存在 `/api/p45/history/{run_id}` 或 replay endpoint，也需透传。

## 输出要求

```json
{
  "btc_timescale_judge": {
    "schema_version": "p45.btc_timescale_judge.v2.1",
    "horizons": {},
    "cross_horizon": {}
  }
}
```

## DoD

1. dashboard latest 返回 `btc_timescale_judge`。
2. overview latest 返回 `btc_timescale_judge`。
3. history/replay 返回历史对应 `btc_timescale_judge`。
4. 缺失新字段时 API 不报错，保留旧 `horizon_views` fallback。
5. 契约校验脚本通过。

## 验收命令

```powershell
.\.venv\Scripts\python.exe scripts\validate_p5_dashboard_contract.py --base-url http://127.0.0.1:8118
```

## 关联任务

P4.5-C43, P8-C34, P5-C61

## 验收记录

- `dashboard/latest` 已透传 `btc_timescale_judge`。
- `overview/latest` 已透传 `btc_timescale_judge`。
- `history/{final_run_id}` 已透传 `btc_timescale_judge`。
- `validate_p5_dashboard_contract.py` 通过。
