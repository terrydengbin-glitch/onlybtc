# P4-C11 LLM 与总控 Mock 与 DoD 验收

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## 2026-05-21 执行记录

已完成 P4 Mock / DoD 验收硬门禁：

- 新增 `onlybtc.audit.p4_dod.run_p4_dod_check`。
- 新增 CLI：`p4-dod-check`。
- DoD 检查项覆盖：
  - P4 HTML 是否存在；
  - final controller JSON 是否存在；
  - Evidence Pack 是否存在且有 evidence；
  - 4 个 Analyst vote 是否落库；
  - vote 是否保留 evidence；
  - cross-exam challenge 是否存在；
  - judge synthesis 是否存在；
  - adversarial review 是否通过；
  - snapshot modules 是否生成；
  - final JSON 必填字段是否齐全；
  - final JSON 展示层是否无交易建议敏感词；
  - state constraints 是否被保留。

真实验证：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

结果：

- `status=passed`
- `passed_count=12`
- `failed_count=0`
- `snapshot_id=snapshot-55cf48e5c216`
- `debate_id=debate-d60e56a30aa4`
- `evidence_pack_id=p4-pack-20260521092336-8615f4`
- `p4_html_path=reports/p4-controller-audit-report.html`

测试：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_full_chain_audit.py
```

结果：`1 passed`。

## 所属 Phase

P4 LLM 推理与总控融合

## 任务目标

用固定 Evidence Pack 和 mock LLM response 验证模块推理、多模型讨论、主裁判合成、反方审查与最终 JSON 输出。P4-C11 未通过，不进入 P9 / P5。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)
- [P4-C12](p4-c12-p4全链条复盘与真实数据契约对齐.md)

## 实施范围

- 验证模块 LLM 输入输出 Schema。
- 验证 Prompt 必须引用 evidence_id，禁止脱离数据自由发挥。
- 验证多模型讨论流程。
- 验证观点不一致时的分歧归因、少数意见保留、主裁判合成。
- 验证反方审查可以要求修正或阻断发布。
- 验证最终总控 JSON 满足 Dashboard、Overview、Article 所需字段。

## 输入

- P4-C01 至 P4-C10。
- P1/P2/P3 mock 或 full-chain run 生成的 SQLite 数据。
- P8 seed data。
- P3 alerts、invalidations、event windows、anomalies、divergences。

## 输出

- mock evidence pack。
- mock model votes。
- debate rounds fixture。
- judge synthesis fixture。
- adversarial review fixture。
- P4 DoD 验收清单。
- `reports/p4-controller-audit-report.html`。

## 2026-05-21 全链条对齐补充

P4 Mock / DoD 不再允许孤立手写 demo：

- mock evidence pack 必须来自 P8 seed 或 P1/P2/P3 mock/full-chain run。
- 必须验证 P4-C01 至 P4-C10 的真实字段契约。
- 必须验证 `run_mode_integrity_invalidation`、business lagging、true/suppressed conflict 能进入 P4 解释与审查。
- 必须生成 P4 独立审计 HTML：`reports/p4-controller-audit-report.html`。
- P4-C11 通过前，不应进入 P9/P5 的真实总控页面开发。

## 2026-05-21 Agent 化重构补充

P4-C11 的 mock 验收对象升级为 Agent workflow：

- P4-C01 analyst/cross-exam/judge/adversarial schema。
- P4-C02 4 个 analyst prompt。
- P4-C06 4 个 Analyst Agent mock outputs。
- P4-C07 mock challenge/revision。
- P4-C08 mock Judge Agent synthesis。
- P4-C09 mock adversarial review。
- P4-C10 final controller JSON。
- P4-C15 runtime adapter 的 mock provider。
- P4-C16 审计 HTML。

验收必须证明 mock runtime 与真实 runtime 共享同一输入、Schema、guardrail 和 SQLite 落库路径。

## 验收标准

- 所有 LLM 输出均可被 JSON Schema 校验。
- 每个观点必须带 evidence_id 和 confidence。
- 多模型分歧不能被简单投票吞掉，必须有分歧等级和少数意见。
- 反方审查失败时 `publish_allowed=false`。
- 最终 JSON 可写入 `judge_syntheses` 和 `dashboard_snapshots`。
- P4 DoD 全部通过后，才允许进入 P9 / P5。

## 依赖任务

P4-C01、P4-C02、P4-C03、P4-C04、P4-C05、P4-C06、P4-C07、P4-C08、P4-C09、P4-C10、P4-C12

## 备注

真实 LLM 不稳定时，使用 mock response 做契约测试；真实模型调用另做集成测试。
