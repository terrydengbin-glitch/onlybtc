# P4-C26 Agent Runtime Provider、Schema Repair 与 No-Fallback 文章运行门控

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态
DONE

## 所属 Phase

P4 Agent 推理与总控融合

## 背景

P4-C25 已确认 Article Writer 可以真实调用 LLM 并生成中文长文，但最新 P4 live+LLM 报告仍显示 `llm_runtime_integrity=fallback_used`。这会直接污染最终研究文章，让正文反复解释 runtime fallback、timeout、schema validation，而不是集中输出高价值业务判断。

当前主要问题：

- `liquidity_flow_analyst` 真实 LLM 调用出现 `ReadTimeout`。
- `onchain_market_structure_analyst` 使用 Kimi 时出现 400。
- `cross_examiner_agent` 和 `CrossExamRevision` 存在 LLM 返回 JSON 外包一层导致 schema validation failed。
- `adversarial_reviewer_agent` 仍可能指向未配置 key 的 provider。
- Runtime fallback reason 过长，直接进入 Final Controller / HTML / final article 上下文，降低文章可读性。

## 任务目标

让 P4 Agent runtime 在 live+LLM 模式下尽量做到 no-fallback，并且在仍然发生失败时，向 Article Writer 暴露的是结构化、短摘要、可解释的质量状态，而不是长 stack trace。

## 实施范围

1. Provider 配置治理
   - 检查 `.env` 中四个 analyst、cross-exam、judge、adversarial、article writer 的 provider/model 映射。
   - 修正 adversarial reviewer 默认 provider，避免指向未配置 key 的 `openai`。
   - 对 Kimi 400 做 provider/model 兼容性确认，必要时切换到可用模型或降级到 deepseek/qwen。

2. Schema repair
   - 对 LLM 返回 `{candidate_challenge: {...}}`、`{cross_exam_revision: {...}}` 等外包一层结构做 unwrap。
   - 对常见字段缺失做可审计的 repair，而不是直接 fallback。
   - repair 后仍需经过 Pydantic schema validation。

3. Timeout / retry 策略
   - 为超时类错误增加有限重试。
   - 将 retry 次数、耗时、最终 provider 写入 runtime trace。
   - 避免单个 Agent 超时拖垮全链条。

4. Runtime summary 分层
   - Final Controller 保留结构化 runtime summary。
   - HTML 保留详细 runtime trace。
   - Article Writer 只消费短摘要：`passed / repaired / fallback_used / failed`，不直接消费长错误堆栈。

5. DoD
   - 增加 `p4_runtime_no_unexpected_fallback` 或等价检查。
   - 在 live+LLM 模式下，Article Writer 的高价值文章不应因非文章阶段 stack trace 被污染。

## 验收标准

- P4 live+LLM 运行后，若 provider key 正常：
  - `article_runtime_mode=llm`
  - `runtime_mode=llm`
  - `fallback_used=false` 或仅有明确可解释的非关键 fallback
  - cross-exam / revision 不再因为外包 JSON 结构直接失败
- Final article 不再大段输出 Pydantic validation stack trace。
- P4 DoD 通过。
- 如果仍有 provider 失败，HTML 能显示短摘要与详细 appendix，而正文只描述其对可信度的影响。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --run-mode live --runtime-mode llm --article-runtime-mode llm
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

## 依赖

P4-C18、P4-C20、P4-C21、P4-C25
