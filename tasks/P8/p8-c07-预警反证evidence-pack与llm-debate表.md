# P8-C07 预警、反证、Evidence Pack 与 LLM Debate 表

## 状态

DONE

## 所属 Phase

P8 SQLite 数据库与持久化层

## 任务目标

建立预警、反证、Evidence Pack、多 LLM Debate、主裁判和反方审查的持久化结构。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- algorithm_alerts、alert_events。
- invalidation_conditions、invalidation_events。
- evidence_packs、evidence_items、evidence_metric_links。
- llm_debates、llm_rounds、llm_model_votes、llm_challenges。
- judge_syntheses、adversarial_reviews。
- 所有 evidence 必须有 evidence_id 和 data link。
- debate 必须关联同一份冻结 Evidence Pack。

## 输入

- P3 预警与反证结果。
- P4 Evidence Pack 与 LLM Debate 结果。

## 输出

- Alert / Invalidation / Evidence / Debate 表。
- 对应 Repository 查询。

## 验收标准

- Alerts 页面能查到支持证据和冲突证据。
- Invalidation 页面能查到触发距离和动作。
- LLM Debate 页面能按轮次回放。
- 主裁判结果和少数派反证可审计。

## 依赖任务

P8-C06、P3-C06、P4-C05

## 备注

LLM 观点不能脱离 evidence_id 保存关键结论。
