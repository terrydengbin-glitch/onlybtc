# P9-C38 Invalidation Workbench v2 API 透传

状态：DONE

## 目标

升级 `/api/p45/invalidation/latest`，使其优先返回 `p45.invalidation_workbench.v2`，同时兼容旧版 `invalidation_rules` / `confirmation_rules` 字段，确保前端可平滑迁移。

## 输入

```text
latest final_payload
final_payload.invalidation_workbench
final_payload.invalidation_rules
final_payload.confirmation_rules
final_payload.btc_trend_cockpit
run_lineage
```

## API 输出

```json
{
  "schema_version": "p45.invalidation_workbench.v2",
  "run_lineage": {},
  "current_thesis": {},
  "validation_state": "confirmed|watching|refuted|conflict|blocked",
  "validation_reason": "",
  "scores": {},
  "btc_response": {},
  "module_evidence_matrix": [],
  "rule_groups": {},
  "triggered_rules": [],
  "armed_rules": [],
  "blocked_rules": [],
  "timeline": [],
  "legacy": {
    "invalidation_rules": [],
    "confirmation_rules": []
  }
}
```

## 兼容策略

1. 如果 `final_payload.invalidation_workbench.schema_version = p45.invalidation_workbench.v2`，API 直接透传。
2. 如果 v2 缺失，API fallback 到旧结构：
   - `schema_version = p45.invalidation.v1`
   - 保留 `invalidation_rules` / `confirmation_rules`
   - `validation_state = watching`
3. API 不在 P9 重算业务结论，只做结构化透传与 fallback。

## DoD

1. `/api/p45/invalidation/latest` 返回 v2 schema。
2. 返回 `current_thesis`、`validation_state`、`scores`、`btc_response`、`module_evidence_matrix`、`rule_groups`、`timeline`。
3. 旧字段 `invalidation_rules` / `confirmation_rules` 仍可被旧前端读取。
4. v2 缺失时 fallback 不报错。
5. FastAPI targeted tests 通过。
6. P5 dashboard contract 验收通过。
