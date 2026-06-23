# P7-C03 Prompt Version Management Report

- schema_version: `p7.c03.prompt_version_registry.v1`
- generated_at: `2026-06-22T23:39:44.194636+00:00`
- applied_to_production: `False`
- entry_count: `8`
- validation_passed: `True`

## Guardrails

- registry_only
- does_not_modify_prompt_text
- does_not_modify_llm_runtime
- does_not_modify_state_machine
- does_not_emit_trading_advice
- requires_p7_c08_before_production_apply

## Coverage

- p45_mainline: `2`
- legacy_compat: `6`

## Entries

| prompt_id | version | scope | status | hash | schema |
|---|---|---|---|---|---|
| p4.adversarial_reviewer.review | p4.agent_prompt.v1 | legacy_compat | legacy_compat | `c8df82552cf67425` | AdversarialReview |
| p4.analyst_agent.independent_review | p4.agent_prompt.v1 | legacy_compat | legacy_compat | `4ec3227083415e60` | AnalystOutput |
| p4.article_writer.analyst_article | p4.agent_prompt.v1 | legacy_compat | legacy_compat | `b53916e9d9eaa660` | AnalystReadableArticle |
| p4.article_writer.final_observation | p4.agent_prompt.v1 | legacy_compat | legacy_compat | `c612e40acbf6c19d` | FinalObservationArticle |
| p4.cross_examiner.challenge | p4.agent_prompt.v1 | legacy_compat | legacy_compat | `186f3f91aada5dce` | CrossExamChallenge |
| p4.judge.synthesis | p4.agent_prompt.v1 | legacy_compat | legacy_compat | `79a6dc9687e60871` | JudgeSynthesis |
| p45.llm_analyst_writer.article | p45.llm_analyst_articles.prompt.v1 | p45_mainline | active | `961a14d172c54a55` | P45_LLM_ANALYST_ARTICLES_SCHEMA_VERSION:p45.llm_analyst_articles.v1 |
| p45.llm_research_writer.article | p45.llm_research_article.prompt.v1 | p45_mainline | active | `29cdeedbda1a71f1` | P45_LLM_RESEARCH_ARTICLE_SCHEMA_VERSION:p45.llm_research_article.v1 |

## Validation Failures

- none

## Notes

- This registry is audit-only and does not modify live prompt text.
- P4 entries are registered as legacy compatibility surfaces.
- P4.5 research and analyst writer prompts are registered as current mainline surfaces.
