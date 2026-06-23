# P5-C38 Dashboard deterministic 结论先行展示、LLM 异步补全与 Run 模式开关

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

当前 Dashboard 的核心结论来自后端确定性链路：

```text
P1 collect -> P2 radar -> P3 scoring -> P4.5 deterministic final
```

LLM 深度研报和四分析师文章只是解释层，不应该阻塞 Dashboard 主结论。盘中高频运行时，用户需要快速得到 final_view、Radar module 状态、时间尺度、反证/确认条件和 Evidence；LLM 发文可以按需异步补全，或本轮直接跳过。

## 目标

- 在 `Run Full Chain` 按钮旁增加轻量 LLM 开关。
- 开关亮起时：本轮跑 deterministic final 后继续后台异步补全 LLM research / analyst articles。
- 开关关闭时：本轮只跑到 P4.5 deterministic final，不跑 LLM 发文。
- 无论是否跑 LLM，P4.5 deterministic final 完成后 Dashboard 主结论立即刷新。
- Article 页和 Run Logs 明确区分 deterministic 主结论与 LLM internal reference。

## 业务规则

```text
LLM on:
  P1/P2/P3/P4.5 deterministic final 完成 -> Dashboard 立即刷新
  p45_llm_research / p45_llm_analysts 后台继续运行
  文章区显示 writing / completed 状态

LLM off:
  P1/P2/P3/P4.5 deterministic final 完成 -> Dashboard 立即刷新
  p45_llm_research / p45_llm_analysts 标记 skipped
  文章区显示本轮未生成 LLM 附录
```

## UI 契约

- 顶部按钮区显示：

```text
[LLM 开关] [Run Full Chain]
```

- 开关状态：
  - 亮：`LLM on`
  - 暗：`fast only`
- tooltip：
  - `LLM on: 结论先出，研报后台补全`
  - `Fast only: 只跑确定性结论，不生成 LLM 文章`
- Run Logs 阶段卡：
  - deterministic 阶段完成后可显示 `decision ready`
  - LLM 阶段运行中显示 `writing`
  - LLM 关闭时显示 `skipped`

## 前端实现范围

- `frontend/src/api.ts` / `api.js`
  - `startP45FullWithLlmJob()` 支持 `skip_llm` 或 `execution_profile` 参数。
- `frontend/src/store.ts` / `store.js`
  - 保存 run 模式开关状态。
  - job polling 期间发现 `p45_final` 完成后触发一次 latest Dashboard refresh。
  - LLM 阶段继续轮询，但不阻塞主结论显示。
- `frontend/src/App.vue`
  - 增加 LLM 开关。
  - Run Logs / Article 页显示 LLM pending / skipped / completed。
  - Dashboard 主结论不依赖 LLM payload。

## DoD

- LLM 开关关闭时，Run Full Chain 不触发 LLM research / analyst 写作。
- LLM 开关开启时，P4.5 deterministic final 完成后 Dashboard 先刷新，LLM 完成后文章区再补全。
- Run Logs 能明确显示 deterministic ready 与 LLM writing/skipped/completed。
- Article 页不会把 LLM internal reference 当作 canonical final view。
- `npm run build` 通过。

## 关联任务

P9-C17, P5-C07, P5-C15, P5-C20, P5-C37, P4.5-C17, P4.5-C18

## Execution Record

- Added a top-bar `LLM on` / `Fast only` run-mode toggle next to `Run Full Chain`.
- The toggle is persisted in localStorage and controls the next full-chain run.
- `LLM on` starts `execution_profile=full_with_llm`.
- `Fast only` starts `execution_profile=fast_deterministic` and sends `skip_llm=true`.
- Job polling refreshes the latest Dashboard payload as soon as `decision_ready=true`, before LLM appendix completion.
- Run Logs now labels the execution profile and LLM status so deterministic readiness is separated from LLM writing/skipped/completed.
- Latest Dashboard refresh now assigns each resolved endpoint immediately, so `dashboard.latest` can update the BTC core card before slower evidence / LLM appendix endpoints finish.
- Page mount now hydrates latest Dashboard data before run-job recovery, avoiding `jobs/latest` SQLite/API contention before the BTC core card can render.
- `dashboard.latest` is requested as the first hydration packet before secondary latest endpoints, preventing bulk evidence / article / event requests from delaying the BTC core card under SQLite/API contention.

## Verification

- `npm run build`
- Result: build passed.
