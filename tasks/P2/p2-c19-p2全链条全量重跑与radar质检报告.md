# P2-C19 P2 全链条全量重跑与 Radar 质检报告

## 状态

DONE

## 所属 Phase

P2 全量雷达模块 / P1-C22 数据链路审计 / P8 SQLite 落库验收

## 背景

P2 已经完成全量雷达模块、P1/P8/SQLite 审计链路对齐与 `onchain_valuation` 质量口径修复。后续每次修改 P1 数据源、P2 雷达规则、P8 落库结构或 P5/P9 展示契约时，都需要一个统一入口重新跑完整业务链条，并同时产出：

- P1-C22 真实数据全链路 HTML 报告
- P2 独立 Radar 质检 HTML 报告

仅依赖 P1-C22 报告不够，因为它主要验收数据源、指标、SQLite 状态与 Radar 消费概览；P2 还需要独立检查每个 radar module 的质量拆解、feature 覆盖、provider_required 缺口、SQLite 三表落库契约。

## 目标

新增 P2 全链条全量重跑脚本，作为 P2 phase gate 的统一验收入口：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\p2-full-audit.ps1
```

或直接调用 CLI：

```powershell
.\.venv\Scripts\python -m onlybtc.cli p2-full-audit
```

## 交付内容

### 1. P2 Full Audit 后端模块

新增：

- `backend/src/onlybtc/audit/p2_full_chain.py`

职责：

- 调用 `run_p1_c22_audit()`，生成 P1-C22 数据链路 HTML 报告。
- 全量调用 `analyze_radars()`，生成新的 P2 radar run。
- 读取 `radar_outputs`、`feature_values`、`module_json_outputs`。
- 生成独立 P2 Radar 质检 HTML。

### 2. CLI 命令

新增：

```powershell
.\.venv\Scripts\python -m onlybtc.cli p2-full-audit
.\.venv\Scripts\python -m onlybtc.cli p2-full-audit --no-collect-live
```

输出必须包含：

- `p1_c22_html_path`
- `p2_radar_run_id`
- `p2_html_path`
- `module_count`
- `low_quality_modules`
- `missing_metric_count`
- `provider_required_count`
- `sqlite_checks`

### 3. PowerShell 包装脚本

新增：

- `scripts/p2-full-audit.ps1`

支持：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\p2-full-audit.ps1
powershell -ExecutionPolicy Bypass -File scripts\p2-full-audit.ps1 -NoCollectLive
```

### 4. P2 独立 HTML 报告

生成：

- `reports/p2-radar-quality-report.html`

报告必须覆盖：

- P2 radar run id
- P1-C22 HTML 路径
- SQLite contract：
  - `radar_outputs`
  - `module_json_outputs`
  - `feature_values`
  - expected module / feature count
- Module Quality：
  - `signal`
  - `strength`
  - `confidence`
  - `data_quality`
  - `overall_score`
  - `coverage_score`
  - `raw_coverage_score`
  - `source_quality_score`
  - `missing_metrics`
  - `provider_required_metrics`
  - `main_discount_reasons`
- Feature Quality：
  - `metric_id`
  - `available`
  - `source_id`
  - `quality_score`
  - `evidence_tier`
  - `quality_blocking`
  - `collection_freshness_status`
  - `business_recency_status`

## 验收结果

已实现并通过：

```powershell
.\.venv\Scripts\python -m pytest backend/tests -q
.\.venv\Scripts\python -m ruff check backend/src/onlybtc/audit/p2_full_chain.py backend/src/onlybtc/cli.py backend/tests/test_p2_full_chain_audit.py
powershell -ExecutionPolicy Bypass -File scripts\p2-full-audit.ps1 -NoCollectLive
```

实际输出：

```text
p1_c22_html_path = reports/p1-c22-真实数据全链路验收报告.html
p2_html_path = reports/p2-radar-quality-report.html
module_count = 14
sqlite_checks.radar_outputs_ok = true
sqlite_checks.module_json_outputs_ok = true
sqlite_checks.feature_values_ok = true
```

## DoD

- P2 全链条重跑有单一命令入口。
- P1-C22 HTML 与 P2 Radar 质检 HTML 均能生成。
- P2 质检报告能独立解释 radar quality 与 feature quality。
- SQLite 三表落库契约在报告中可见。
- `task index.md` 与开发文档同步记录。
