# P8-C17 / run_mode 历史混用归档与生产窗口审计口径治理

## 状态

DONE

## 背景

SQLite 历史库中存在 live/mock/test/unknown 混合样本，但最新生产 collect run 本身是 live-only。旧口径容易把“历史库风险”误表达成“当前生产 run 污染”。

## 修改内容

1. P1-C22 run mode 审计拆分为：
   - `current_run`: 只检查当前 collect run 是否 live-only。
   - `history`: 检查全库历史 live/mock/test/unknown 混用。
2. 当前 run 不是 live-only 时，才作为 production blocker。
3. 历史混用继续作为 `run_mode_mixed_history` warning 保留，但文案明确“不污染当前 run”。
4. Data Quality API 新增 `run_mode_integrity`：
   - `current_run`
   - `history`
   - `default_query_scope=live_only`
   - `history_replay_all_requires_explicit_run_mode=true`
5. History Replay API 返回 `run_mode_scope` 和当前 payload 的 `run_mode_integrity`，说明默认 live-only，混合样本必须显式选择 `run_mode=all`。

## DoD

- [x] 当前 live-only run 不再被历史 mock 数据标记为生产 blocker。
- [x] P1-C22 同时展示 current run 与 historical run_mode risk。
- [x] `run_mode_mixed_history` 保留为 non-blocking warning。
- [x] Data Quality API 返回当前 run、历史 run_mode 计数与默认查询作用域。
- [x] History Replay 返回 run mode scope，并声明 `run_mode=all` 必须显式选择。
- [x] P3 默认 live-only 不变。
- [x] 相关测试通过。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p1_c22_audit.py backend/tests/test_p45_dashboard_api.py::test_data_quality_source_health_failed_count_filters_healthy_runs -q
```

