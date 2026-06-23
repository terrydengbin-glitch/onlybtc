# P5-C09 BTC Detail Overview 子页面

## 状态

DONE

## 所属 Phase

P5 Dashboard 与可视化层

## 当前架构对齐

BTC Overview 子页面以 P4.5 Report v2 为主契约，通过 `GET /api/p45/overview/latest` 与 Dashboard 已加载的 evidence/radar 数据渲染，不直接读取 SQLite。

核心字段：

- `final_view` / `final_view_cn`
- `decision_card`
- `aggregation_audit`
- `horizon_views`
- `invalidation_rules`
- `confirmation_rules`
- `research_article`
- `publish_article`
- `run_lineage`

## 任务目标

实现 BTC Detail Overview 子页面，用于解释当前 BTC 总控状态、关键驱动、冲突证据、置信度折扣、风险构成、观点改变条件与 Watch Next。

## 实施范围

- Current State：展示方向分、raw net、支撑/压力、零分占比、不可用比例、risk mode。
- Key Drivers / Conflicting Evidence：展示 support drivers 与 pressure drivers，并可点击跳转 Evidence detail。
- Confidence Explanation：展示 `score_normalization`、阈值、confidence penalty、data quality。
- What Would Change The View：展示 invalidation / confirmation rules，并可跳转 Invalidation 页面。
- Run Lineage：展示 collect / P2 / P3 / P4.5 run id，避免跨 run 误读。
- 保留 24h / 3d / 7d 周期视图、why_not_strong 与原有入口。

## 输出

- 更新 [App.vue](../../frontend/src/App.vue)
- 更新 [styles.css](../../frontend/src/styles.css)
- 更新 [validate_p5_page_dod.py](../../scripts/validate_p5_page_dod.py)

## 验收标准

- 页面使用 API DTO 渲染，不直接拉 SQLite。
- 关键驱动和冲突证据均可点击追溯。
- 不输出交易计划类语言，不引入仓位、杠杆、止损、止盈等逻辑。
- Overview 必须解释 confidence 为什么被降低或被封顶。
- Overview 必须展示 run lineage。

## 验收记录（2026-05-22）

```powershell
npm run build
.\.venv\Scripts\python.exe scripts\validate_p5_dashboard_contract.py
.\.venv\Scripts\python.exe scripts\validate_p5_page_dod.py
```

结果：

- 前端 build passed。
- P5 Dashboard contract validation passed。
- P5 page DoD validation passed。

## 备注

本页仍遵循 P4.5 的 `final_view`，不绕过反证/确认规则、预警等级或数据质量边界。
