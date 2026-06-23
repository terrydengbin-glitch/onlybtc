# P8-C08 文章、快照、History Replay 与评分表

## 状态

DONE

## 所属 Phase

P8 SQLite 数据库与持久化层

## 任务目标

建立文章、Dashboard 快照、历史回放、后续评分和校准备注的持久化结构。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- articles、article_versions、article_evidence_links。
- dashboard_snapshots、snapshot_modules、snapshot_alerts。
- replay_scores：24h、72h、7D、Signal Validity、Alert Validity、Confidence Calibration。
- calibration_notes：误报、漏报、阈值建议、权重建议。
- snapshot 必须冻结当时状态，不读取当前实时数据。

## 输入

- P4 总控 JSON。
- P5 Dashboard 状态。
- P6 文章与评分流程。

## 输出

- Article / Snapshot / Replay 表。
- History Replay 聚合查询。

## 验收标准

- 每次完整 pipeline 可以生成 dashboard_snapshot。
- 历史文章能关联当时 evidence_pack、debate、snapshot。
- History Replay 不被当前数据污染。
- 评分结果可用于 P7 校准。

## 依赖任务

P8-C07、P4-C10、P6-C01

## 备注

评分命名禁止使用 Call Accuracy。
