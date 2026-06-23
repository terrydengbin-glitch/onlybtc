# P9-C17 Run Full Chain execution_profile、skip_llm 契约与阶段状态治理

## 状态

DONE

## Phase

P9 FastAPI 聚合 API 与运维质控

## 背景

前端需要支持两类 Run Full Chain：

```text
fast_deterministic:
  只跑 P1/P2/P3/P4.5 deterministic final，用于高频快速分析。

full_with_llm:
  deterministic final 先完成并可被前端读取，随后异步补全 LLM research / analyst articles。
```

当前后端已有 `skip_llm`、`skip_research_llm`、`skip_analyst_llm` 参数，但前端模式语义、阶段状态、P4.5 final 完成后的中间可读状态还需要显式契约化。

## 目标

- 为 `/api/p45/run-full-with-llm/jobs` 增加统一运行模式契约。
- 支持 `execution_profile=fast_deterministic | full_with_llm`。
- 保留兼容参数 `skip_llm / skip_research_llm / skip_analyst_llm`。
- P4.5 deterministic final 完成后，job status 立刻暴露 `decision_ready=true` 和 `final_run_id`。
- LLM 关闭时，LLM 阶段稳定标记为 `skipped`，不是 pending / failed。
- LLM 开启时，LLM 阶段失败只能导致 `completed_with_llm_errors`，不影响 deterministic 主结论。

## API 契约

### 请求

```text
POST /api/p45/run-full-with-llm/jobs?execution_profile=fast_deterministic
POST /api/p45/run-full-with-llm/jobs?execution_profile=full_with_llm
```

兼容：

```text
POST /api/p45/run-full-with-llm/jobs?skip_llm=true
POST /api/p45/run-full-with-llm/jobs?skip_research_llm=true&skip_analyst_llm=true
```

### Job Status 响应新增字段

```json
{
  "execution_profile": "fast_deterministic",
  "decision_ready": true,
  "deterministic_ready_at": "...",
  "llm_enabled": false,
  "llm_status": "skipped",
  "run_lineage": {
    "final_run_id": "p45final-...",
    "llm_research_run_id": null,
    "llm_analyst_run_id": null
  }
}
```

### 阶段状态

```text
p1_collect: pending/running/completed/failed
p2_radar: pending/running/completed/failed
p3_scoring: pending/running/completed/failed
p45_final: pending/running/completed/failed
p45_llm_research: pending/running/completed/skipped/failed
p45_llm_analysts: pending/running/completed/skipped/failed
audit_reports: pending/running/completed/failed
```

## 后端实现范围

- `backend/src/onlybtc/api/app.py`
  - job endpoint 接收 `execution_profile`。
- `backend/src/onlybtc/api/p45_jobs.py`
  - 将 execution profile 映射到 skip flags。
  - 在 `p45_final` 完成后写入 job result / run_lineage。
  - LLM skipped 阶段写清楚原因。
  - job status 暴露 `decision_ready`。
- 测试覆盖：
  - `fast_deterministic` 不产生 LLM rows。
  - `full_with_llm` 产生 LLM rows。
  - LLM 失败不覆盖 deterministic final。

## DoD

- `fast_deterministic` 模式下，P4.5 deterministic final 正常生成，LLM 阶段为 skipped。
- `full_with_llm` 模式下，P4.5 final 完成后 job status 已含 final_run_id，LLM 阶段可继续 running。
- 前端能根据 `decision_ready=true` 立即刷新 Dashboard 主结论。
- 旧参数 `skip_llm=true` 仍可用。
- FastAPI 集成测试通过。

## 关联任务

P5-C38, P9-C15, P9-C16, P9-C07, P4.5-C17, P4.5-C18

## Execution Record

- Implemented `execution_profile=full_with_llm|fast_deterministic` mapping in the P4.5 full-chain background job.
- `fast_deterministic` now forces LLM research and analyst stages to `skipped`.
- Job status now exposes `execution_profile`, `decision_ready`, `deterministic_ready_at`, `llm_enabled`, and `llm_status`.
- P4.5 deterministic final checkpoints the job result/run lineage before LLM work continues.
- FastAPI job endpoint accepts `execution_profile` while keeping `skip_llm` compatibility.

## Verification

- `.\.venv\Scripts\python.exe -m pytest backend/tests/test_p45_dashboard_api.py -q`
- Result: `8 passed`.
