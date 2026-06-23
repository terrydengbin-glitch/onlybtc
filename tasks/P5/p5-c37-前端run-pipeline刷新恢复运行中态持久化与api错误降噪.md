# P5-C37 前端 Run Pipeline 刷新恢复、运行中态持久化与 API 错误降噪

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

当前前端点击 `Run Full Chain` 后调用长请求 `runFullChain()`。如果用户在 pipeline 运行期间刷新页面，前端内存中的 `state.running`、`state.runResult` 和当前 stage 会丢失。页面重新加载后会并发读取 latest payload，并可能显示旧 final 或触发 stale evidence 404。

## 根因

```text
Run Full Chain 点击
  -> state.running=true
  -> 长 POST 绑定当前页面生命周期
  -> 刷新页面
  -> state.running 丢失
  -> refreshLatest() 并发读取 latest
  -> route context / evidence detail 可能仍指向旧 run
  -> API errors 暴露到页面
```

## 目标

- 前端改为调用 P9-C15 提供的后台 job API。
- 将 `active_job_run_id` 持久化到 `localStorage` 或 `sessionStorage`。
- 页面刷新后自动恢复 running job，并进入/保持 Run Logs 页面。
- 运行中状态与 latest completed Dashboard 分离展示。
- 对可恢复的 optional API error 降噪，不让页面出现“无数 API 错误”。

## 实施范围

### 状态管理

- 新增 `state.activeRunJob`、`state.activeRunJobId`、`state.runPolling`。
- `runFullChain()` 改为：

```text
POST /api/p45/run-full-with-llm/jobs
  -> 保存 job_run_id
  -> 打开 Run Logs
  -> 轮询 GET /jobs/{job_run_id}
```

- `onMounted()` 时：
  - 先读取本地 `active_job_run_id`。
  - 若存在，调用 `/jobs/{id}` 或 `/jobs/latest`。
  - 若仍 running/queued，恢复轮询。
  - 若 completed/failed，清理或保留最近结果。

### API 错误降噪

- optional latest endpoint 失败不弹主错误。
- running job 期间，旧 latest 与新 running job 的 run_id 不一致时，不把 evidence/detail 404 当作 fatal error。
- API error 面板聚合去重：
  - 同 endpoint/status 在短时间内只显示一次。
  - stale evidence 404 显示为可恢复提示，不刷屏。

### UI

- Run Logs 顶部显示：
  - running / completed / failed
  - current stage
  - job_run_id
  - heartbeat / last updated
- 刷新恢复时显示 “已恢复正在运行的 pipeline”。

## DoD

- 运行 pipeline 时刷新页面，Run Logs 能恢复当前 job 状态。
- 刷新后不会回到空 Dashboard 或旧 running 状态。
- 运行中不出现重复 API error 刷屏。
- 运行结束后自动刷新 latest Dashboard / Article / Evidence。
- `npm run build` 通过。
- P5 页面 DoD 和 Dashboard contract 校验通过。

## 关联任务

P9-C15, P9-C16, P5-C07, P5-C15, P5-C20, P5-C31, P5-C36

## 执行记录

- `frontend/src/api.ts` 新增 P4.5 Full Chain job API client。
- `frontend/src/store.ts` 新增 `activeRunJob / activeRunJobId`，并将运行中 job id 写入 `localStorage`。
- `runFullChain()` 改为启动后台 job，Run Logs 通过 job status 轮询刷新。
- `onMounted()` 增加 `resumeActiveRunJob()`，页面刷新后可恢复 running job，并自动进入 Run Logs。
- optional API error 增加去重，避免刷新或 stale evidence 造成错误刷屏。
- evidence detail 请求携带 `final_run_id/pack_id/allow_stale_fallback`，并在后端返回 resolved id 时更新 route context。

## 验证结果

```text
npm run build
passed
```
