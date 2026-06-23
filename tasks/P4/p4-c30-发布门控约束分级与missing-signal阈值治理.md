# P4-C30 发布门控约束分级与 Missing Signal 阈值治理

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态
DONE

## 所属 Phase
P4 Agent 推理与总控融合

## 背景
当前 `reports/p4-controller-audit-report.html` 主文章中出现“受事件窗口发布约束与缺失主要信号证据限制”。经代码追踪，这不是 LLM 自行判断，而是 P4 规则基线和状态机自动生成的 `blocked_by`：

- `event_window_publish_constraint`
- `missing_primary_signal_evidence`

现有逻辑偏保守：P3 事件窗口只要存在 `event_phase` 或 `publish_impact` 就会生成事件窗口约束；状态机看到该约束后无条件加入 `blocked_by`。同样，P2/P4 evidence 中只要存在 `affects_signal=True` 且 `available=False` 的指标，就会生成 `missing_primary_signal_evidence` 并阻止发布。

这导致两个业务语义混在一起：

1. **需要关注/监控** 被升级成 **阻止发布**。
2. **部分主信号缺失导致信心折扣** 被升级成 **硬阻断**。

P4-C29 已经把文章正文改成趋势洞察优先，但底层门控仍需细化，否则文章仍会被过硬的 `blocked_by` 语义牵引。

## 当前触发原因

### 1. 事件窗口发布约束
来源：

- `backend/src/onlybtc/p4/rule_baseline.py`
- `backend/src/onlybtc/p4/state_machine.py`

本轮触发项包括 CPI / FOMC / NFP / PCE 等事件窗口，其中 PCE 距离约 7.8 天，P3 标记为 `pre_event / monitor`。

问题：`monitor` 语义应该是降低信心、提高观察优先级，不应无条件阻止所有正式发布。

### 2. Missing Primary Signal
本轮缺失项包括：

- `whale_flow`：鲸鱼流量缺失
- `miner_flow`：矿工流量缺失
- `hibor`：HIBOR 缺失
- `regulatory_event_score`：监管事件评分缺失

来源：

- `backend/src/onlybtc/p4/evidence_pack.py`
- `backend/src/onlybtc/p4/rule_baseline.py`
- `backend/src/onlybtc/p4/state_machine.py`

问题：missing feature 当前默认 `role=primary_signal`、`affects_signal=True`，导致 provider-required 或局部缺失也被一刀切升级为硬阻断。

## 任务目标
建立分层发布门控体系，把 `monitor / confidence_discount / block_publish` 明确分开：

1. 事件窗口约束不再一律 `blocked_by`。
2. Missing signal 不再一律 `blocked_by`。
3. `blocked_by` 只代表真正阻止发布候选的硬条件。
4. 文章仍可展示约束，但必须区分“观察提醒”和“发布阻断”。
5. P4 DoD 对新的门控语义进行验证。
6. 明确将 `whale_flow`、`miner_flow`、`hibor`、`regulatory_event_score` 降级为可忽略的 provider-required 缺口：保留审计可见性，但不计入 P4 missing evidence 折扣，也不触发 `missing_primary_signal_evidence`。

## 设计方案

### 1. 事件窗口分级
为 P3 event evidence / P4 rule baseline 引入分级：

- `monitor`：只进入 `watch_flags` 或 `confidence_discount_reasons`。
- `discount_confidence`：降低 confidence，但不进入 `blocked_by`。
- `block_critical_publish`：阻止 critical publish。
- `block_all_publish`：极端情况下阻止所有发布候选。

建议规则：

- T-7 到 T-3：daily watch / monitor。
- T-3 到 T-1：confidence discount。
- T-0 / 重大事件当天：block critical publish。
- Post-event actual 缺失但价格已剧烈波动：block critical publish 或 dashboard-only。

### 2. Missing Signal 阈值治理
为缺失信号增加权重与阈值：

- 单个低权重缺失：仅记录 `missing_signal_warnings`。
- 同一核心模块多个主信号缺失：confidence discount。
- 高权重核心主信号缺失且影响当前方向判断：进入 `blocked_by`。
- provider-required 但长期不可用的代理指标：应降级为 coverage/quality warning，而不是默认硬阻断。
- 本阶段先落地白名单：`whale_flow`、`miner_flow`、`hibor`、`regulatory_event_score` 作为 ignorable provider-required gaps；它们不再进入 `missing_evidence` discount，不再生成 `missing_primary_signal_evidence`，仍保留在 Evidence Appendix 供审计追踪。

建议新增输出字段：

- `missing_signal_warnings`
- `confidence_discount_reasons`
- `soft_constraints`
- `hard_constraints`
- `blocked_by`

### 3. 状态机调整
`state_machine._blocked_by()` 不再直接根据 constraint name 一刀切阻断，而是读取 constraint 的 `publish_impact` / `gate_level`：

- `gate_level=watch`：不进 `blocked_by`
- `gate_level=discount`：不进 `blocked_by`，但影响 confidence
- `gate_level=block_critical_publish`：进入 `blocked_by`
- `gate_level=block_all_publish`：进入 `blocked_by`

### 4. Final Controller 与文章输出
Final Controller 需要区分：

- `publish_allowed`
- `publish_scope`
- `blocked_by`
- `soft_constraints`
- `watch_flags`
- `confidence_discount_reasons`

Article Writer 中：

- 正文可以说“事件窗口需要重点观察”。
- 只有硬阻断时才写“受发布约束阻止”。
- Missing signal 应明确说明是“缺失导致信心折扣”还是“缺失导致发布阻断”。

### 5. HTML / DoD
P4 HTML 增加门控分层展示：

- Soft Constraints
- Confidence Discount Reasons
- Hard Publish Blocks
- Missing Signal Detail
- Event Window Gate Level

DoD 增加检查：

- `monitor` 不应直接进入 `blocked_by`。
- 低权重 missing signal 不应直接进入 `blocked_by`。
- `blocked_by` 非空时必须能追溯到 hard gate。
- 文章正文不得把 soft constraints 写成 hard blocks。

## 验收标准

- PCE/NFP/CPI/FOMC 处于 monitor 阶段时，P4 进入观察/折扣，而不是无条件 `blocked_by`。
- `whale_flow/miner_flow/hibor/regulatory_event_score` 缺失时，根据权重和模块影响分级处理。
- `blocked_by` 只包含真正硬阻断原因。
- HTML 明确区分软约束、信心折扣、硬阻断。
- 主文章不再把所有约束统一写成“发布被限制”。
- P4 DoD 通过。

## 验收结果

- `whale_flow`、`miner_flow`、`hibor`、`regulatory_event_score` 已降级为 ignorable provider-required gaps。
- 最新 P4 Evidence Pack 校验：
  - `missing_evidence_count=0`
  - `ignored_provider_required_missing_count=4`
  - `missing_primary_signal_evidence` 不再生成
  - 事件窗口约束 `gate_level=watch`
  - 状态机 `blocked_by=[]`
- `backend/tests` 通过：109 passed。
- `ruff check backend/src backend/tests` 通过。

## 验证命令
```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --run-mode live --runtime-mode llm --article-runtime-mode llm
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

## 依赖
P3-C14, P3-C15, P4-C24, P4-C29
