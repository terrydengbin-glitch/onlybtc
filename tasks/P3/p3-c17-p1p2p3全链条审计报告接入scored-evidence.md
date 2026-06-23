# P3-C17 P1/P2/P3 全链条审计报告接入 Scored Evidence

## 状态

DONE

## 所属 Phase

P3 状态机、风险与事件窗口 / P4.5 Radar Scored Analyst Writer 前置验收

## 背景

P3-C11 已完成 `p1p2p3全链条全量重跑与p3审计报告`，能真实跑通 P1/P2/P3 并输出 P3 审计 HTML。现在 P3-C16 新增了指标级 `ScoredMetricEvidence` 和 Radar 板块级 `ScoredRadarModule` 契约，P3-C11 原报告需要升级，才能让 P4.5 在实现前就能从审计报告中检查：

- 每个 Radar 板块是否有总分。
- 每个 Radar 板块是否有 `bullish / bearish / neutral / mixed` 方向。
- 每个指标是否有正分、负分、零分或不可用分桶。
- 每个指标是否有一句话解释和评分原因。
- P4.5 输入是否可以从 P3 报告完整追溯。

## 任务目标

优化 P3 全链条全量重跑审计脚本与报告，使其在真实运行时同步输出：

```text
P1 HTML: 真实数据全链路验收报告
P2 HTML: Radar 质检报告
P3 HTML: 算法审计 + Scored Evidence / Scored Radar Module 报告
```

并在 P3 HTML 中新增 P4.5 前置检查区。

## 实施范围

1. P3-C11 脚本升级
   - 保持原有 P1/P2/P3 全链条重跑能力。
   - 明确输出本 run 的 P1/P2/P3 HTML 路径。
   - run lineage 必须展示：
     - `collect_run_id`
     - `p2_radar_run_id`
     - `p3_run_id`

2. P3 HTML 新增 Radar 板块评分区
   - 展示每个 Radar 模块：
     - `module_score`
     - `module_direction`
     - `module_strength`
     - `module_confidence`
     - `module_quality_score`
     - 正分/负分/零分/不可用指标数量
     - top positive / top negative evidence ids
     - `module_explanation`

3. P3 HTML 新增指标级评分区
   - 展示每个指标：
     - `evidence_id`
     - `radar_module`
     - `metric_id`
     - `source_id`
     - `value`
     - `metric_score`
     - `score_bucket`
     - `direction`
     - `quality_score`
     - `metric_explanation`
     - `score_reason`
     - `run_scope`
     - `fallback_used`

4. P4.5 输入预检区
   - 按 4 个分析员分组展示可消费模块：
     - macro_event_analyst
     - liquidity_flow_analyst
     - microstructure_analyst
     - onchain_structure_analyst
   - 每个分析员展示：
     - 模块数量
     - 指标数量
     - positive / negative / zero / unavailable 分布
     - 是否缺少 `module_explanation`
     - 是否缺少 `metric_explanation`

5. 数据边界区
   - 显示 unavailable/provider_required/fallback/low_quality 指标。
   - 明确 `zero` 与 `unavailable` 的区别。
   - live 模式下标明是否全部来自 current_run。

6. 报告输出
   - P1/P2/P3 三个 HTML 必须都由同一次命令生成或刷新。
   - 命令输出中必须打印三个 HTML 路径。
   - 如果 P3-C16 尚未实现，则本卡实现时应以 schema placeholder/empty section 显示“等待 P3-C16 输出”，不能静默缺失。

## 验收标准

- 全链条真实运行后，P1/P2/P3 HTML 均存在且是本 run 输出。
- P3 HTML 能看到 Radar 板块总分和方向。
- P3 HTML 能看到指标级正分、负分、零分、不可用列表。
- P3 HTML 能按 4 个 P4.5 分析员分组预览输入覆盖。
- `zero` 不被当成缺失，`unavailable` 不被当成 0 分。
- P4.5 可以基于 P3 HTML 和 JSON 明确知道自己将消费哪些模块和指标。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests
.\.venv\Scripts\python.exe -m onlybtc.cli p3-full-audit --run-mode live
```

## 依赖

P3-C11, P3-C16, P2-C21, P4.5-C01

## 完成记录

已完成 P3 full audit 报告升级：

- P3 HTML 新增 `Scored Radar Modules`。
- P3 HTML 新增 `Scored Metric Evidence`。
- P3 HTML 新增 `P4.5 Analyst Input Precheck`。
- SQLite contract 新增：
  - `scored_metric_rows`
  - `scored_radar_module_rows`
  - `scored_evidence_ok`
- 全链条输出仍同步刷新：
  - P1 HTML
  - P2 HTML
  - P3 HTML
- P4.5 预检区已按 4 个分析员统计模块数、指标数、positive/negative/zero/unavailable 分布，以及缺失解释检查。

真实运行验证：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p3-full-audit --run-mode live
```

最新 HTML：

- `reports/p1-c22-真实数据全链路验收报告.html`
- `reports/p2-radar-quality-report.html`
- `reports/p3-algorithm-audit-report.html`

最新 run：

- `collect_run_id=collect-20260522051810-e5d57b`
- `p2_radar_run_id=radar-20260522051942-d29de4`
- `p3_run_id=p3-20260522051943-76ec9c`

测试：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests
```

结果：`109 passed`，ruff passed。
