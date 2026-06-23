# P3-C19 P3 审计报告展示 Semantic 评分字段

## 状态

DONE

## 所属 Phase

P3 状态机、风险与事件窗口 / P4.5 Radar Scored Analyst Writer 前置审计

## 背景

P3-C18 已经把 BTC 专业指标评分语义写入 `ScoredMetricEvidence`，并在 SQLite 中保留：

- `base_metric_score`
- `base_direction`
- `semantic_rule_id`
- `semantic_warning`

当前 `reports/p3-algorithm-audit-report.html` 已经展示 `metric_score / direction / metric_explanation / score_reason`，但没有展示上述 P3-C18 新字段。这样 P4.5 可以正常消费数据，但人工审计时无法直接在 HTML 中确认“原始 Radar 分数如何被专业语义校准”。

## 任务目标

增强 P3 审计 HTML，让 P3-C18 的语义评分字段可见、可核对、可追溯。

## 实施范围

1. 在 P3 full-chain audit 的 `Scored Metric Evidence` 表中增加字段：
   - `base_metric_score`
   - `base_direction`
   - `semantic_rule_id`
   - `semantic_warning`
2. 保留现有字段：
   - `metric_score`
   - `score_bucket`
   - `direction`
   - `metric_explanation`
   - `score_reason`
3. 如果字段为空，需要显示为 `-`，不能让 HTML 表格错位。
4. P3 HTML 仍然保持可读，不把 JSON 大段塞进主表。
5. 更新测试，确保 HTML 中包含这些字段名。

## 验收标准

- `reports/p3-algorithm-audit-report.html` 中可以看到：
  - `semantic_rule_id`
  - `semantic_warning`
  - `base_metric_score`
  - `base_direction`
- 最新 P3 run 的 118 条 scored metric evidence 都能展示语义规则。
- 单元测试覆盖 HTML 字段展示。
- `pytest backend/tests/test_p3_full_chain_audit.py -q` 通过。
- `ruff check backend/src backend/tests` 通过。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p3_full_chain_audit.py -q
.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests
.\.venv\Scripts\python.exe -m onlybtc.cli p3-full-audit --run-mode live
```

## 依赖

P3-C16, P3-C17, P3-C18

## 完成记录

已完成 P3 审计 HTML 展示增强：

- `Scored Metric Evidence` 表新增字段：
  - `base_metric_score`
  - `base_direction`
  - `semantic_rule_id`
  - `semantic_warning`
- 保留原有 `metric_score / direction / metric_explanation / score_reason` 展示。
- 测试新增 HTML 字段断言。

验证：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p3_full_chain_audit.py -q
.\.venv\Scripts\python.exe -m ruff check backend/src/onlybtc/audit/p3_full_chain.py backend/tests/test_p3_full_chain_audit.py
.\.venv\Scripts\python.exe -m onlybtc.cli p3-full-audit --run-mode live
```

结果：

- `test_p3_full_chain_audit.py`: 1 passed
- `ruff`: passed
- 真实运行完成：
  - `collect_run_id=collect-20260522060830-52e641`
  - `p2_radar_run_id=radar-20260522061011-5dbc2a`
  - `p3_run_id=p3-20260522061012-01d662`
  - `scored_metric_rows=118`
  - `scored_radar_module_rows=14`

HTML 校验：

- `base_metric_score` 可见
- `base_direction` 可见
- `semantic_rule_id` 可见
- `semantic_warning` 可见
- 118 条 scored metric evidence 均有 `semantic_rule_id`
