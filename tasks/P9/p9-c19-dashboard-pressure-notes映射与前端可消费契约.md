# P9-C19 / Dashboard Pressure Notes 映射与前端可消费契约

## 状态

DONE

## 背景

P4.5-C22 已修复 Fund Flow pressure note 的边际语义：

- ETF 自身没有 `marginal_state=pressure_easing` 时，不再写“ETF 流出压力边际缓和”。
- P4.5 final payload / HTML 已包含正确的 `pressure_notes`。

最新审计发现：

- `reports/p45-research-report.html` 的 P4.5 Final JSON 已有 `pressure_notes`。
- `/api/p45/dashboard/latest` 没有把 `pressure_notes` 映射到前端 DTO。

这意味着报告层已经修好，但 Dashboard API 没有把 P4.5 final payload 的 `pressure_notes` 暴露给前端。

## 目标

把 P4.5 final payload 的 `pressure_notes` 暴露到 Dashboard / Overview 前端消费 API：

1. `/api/p45/dashboard/latest` 返回 `pressure_notes`。
2. `/api/p45/overview/latest` 返回同一份 `pressure_notes`。
3. DTO 保持兼容：没有 pressure note 时返回空数组，不返回 `null`。
4. 前端可以直接消费字段，不需要解析 HTML 或 Final JSON 附录。

## Schema

```json
{
  "pressure_notes": [
    {
      "module": "fund_flow",
      "indicator": "etf_net_flow",
      "type": "absolute_pressure",
      "severity": "medium",
      "message": "ETF 仍处于净流出，绝对资金面偏空；资金流整体存在边际改善，但 ETF 端仍是压力来源。",
      "etf_pressure_easing_confirmed": false
    }
  ]
}
```

## 不改范围

- 不修改 P2/P3/P4.5 评分、聚合和报告生成逻辑。
- 不修改 LLM 运行逻辑。
- 不要求前端立刻新增 UI 展示，只先打通 API 契约。

## DoD

- [x] `/api/p45/dashboard/latest` 返回 `pressure_notes`，且无 note 时为空数组。
- [x] `/api/p45/overview/latest` 返回同一份 `pressure_notes`。
- [x] Dashboard API 测试覆盖：
  - 有 pressure note 时字段内容与 P4.5 final payload 一致。
  - 无 pressure note 时为 `[]`。
  - Overview 与 Dashboard 的 pressure note 一致。
- [x] 不破坏 existing P9-C18 LLM lineage 作用域隔离。

## 验收记录

- `backend/src/onlybtc/api/p45_dashboard.py`
  - `latest_dashboard()` 新增 `pressure_notes` 映射。
  - `latest_overview()` 新增 `pressure_notes` 映射。
- `backend/tests/test_p45_dashboard_api.py`
  - 覆盖 Dashboard / Overview pressure note DTO。
  - 覆盖无 note 时返回 `[]`。
- 测试通过：
  - `.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q`
  - 结果：`10 passed`
