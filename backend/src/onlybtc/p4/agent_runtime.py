from __future__ import annotations

import json
import re
import time
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from onlybtc.core.config import Settings, get_settings
from onlybtc.p4.prompts import PROHIBITED_TRADING_TERMS, PromptBundle
from onlybtc.p4.schemas import (
    AdversarialReview,
    AnalystOutput,
    AnalystReadableArticle,
    CrossExamChallenge,
    CrossExamRevision,
    FinalObservationArticle,
    JudgeSynthesis,
    StrictModel,
)


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model_name: str | None = None
    base_url: str | None = None
    api_key_configured: bool = False
    enabled: bool = False
    disabled_reason: str | None = None
    enable_thinking: bool = False
    timeout_seconds: float | None = None
    max_tokens: int | None = None
    temperature: float | None = None


class GuardrailResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    message: str | None = None


class RuntimeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_run_id: str
    agent_role: str
    agent_name: str
    model_provider: str
    model_name: str | None = None
    prompt_version: str
    schema_version: str | None = None
    trace_id: str
    guardrail_results: list[GuardrailResult]
    structured_output: dict[str, Any] | None = None
    raw_output_ref: str | None = None
    error: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    latency_ms: int
    token_usage: dict[str, int] = Field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.error is None and all(result.passed for result in self.guardrail_results)


class AgentRuntimeAdapter:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.call_count = 0
        self.estimated_tokens_used = 0

    def run_mock(
        self,
        prompt: PromptBundle,
        output_model: type[StrictModel],
        structured_output: dict[str, Any] | None = None,
        fallback_reason: str | None = None,
    ) -> RuntimeResult:
        provider = provider_for_agent(prompt.agent_id, self.settings)
        started = time.perf_counter()
        output = structured_output or _mock_output(prompt, output_model)
        return _build_runtime_result(
            prompt=prompt,
            provider=provider,
            output_model=output_model,
            structured_output=output,
            started=started,
            raw_output_ref=f"mock://{prompt.agent_id}/{uuid4().hex[:8]}",
            fallback_used=fallback_reason is not None,
            fallback_reason=fallback_reason,
        )

    def run_llm_or_mock(
        self,
        prompt: PromptBundle,
        output_model: type[StrictModel],
        fallback_output: dict[str, Any],
    ) -> RuntimeResult:
        result = self.run_openai_compatible_chat(prompt, output_model)
        if result.succeeded or self.settings.p4_llm_fallback_policy == "strict":
            return result
        return self.run_mock(
            prompt,
            output_model,
            structured_output=fallback_output,
            fallback_reason=result.error or "llm_runtime_failed",
        )

    async def run_openai_agents(
        self,
        prompt: PromptBundle,
        output_model: type[StrictModel],
    ) -> RuntimeResult:
        provider = provider_for_agent(prompt.agent_id, self.settings)
        started = time.perf_counter()
        try:
            from agents import Agent, Runner  # type: ignore[import-not-found]
        except ImportError:
            return _error_result(
                prompt=prompt,
                provider=provider,
                started=started,
                error=(
                    "openai-agents is not installed. Install package 'openai-agents' "
                    "before enabling real OpenAI Agents SDK runtime."
                ),
            )
        if not provider.api_key_configured:
            return _error_result(
                prompt=prompt,
                provider=provider,
                started=started,
                error=f"Provider {provider.provider} has no API key configured.",
            )
        if provider.provider != "openai":
            return _error_result(
                prompt=prompt,
                provider=provider,
                started=started,
                error=(
                    "OpenAI Agents SDK runtime currently supports provider=openai only; "
                    f"got {provider.provider}."
                ),
            )

        agent = Agent(
            name=prompt.agent_id,
            instructions=prompt.system_prompt,
            model=provider.model_name,
            output_type=output_model,
        )
        result = await Runner.run(agent, prompt.user_prompt)
        output = result.final_output
        if isinstance(output, BaseModel):
            structured_output = output.model_dump(mode="json")
        elif isinstance(output, dict):
            structured_output = output
        else:
            structured_output = json.loads(str(output))
        return _build_runtime_result(
            prompt=prompt,
            provider=provider,
            output_model=output_model,
            structured_output=structured_output,
            started=started,
            raw_output_ref=f"openai-agents://{prompt.agent_id}/{uuid4().hex[:8]}",
        )

    def run_openai_compatible_chat(
        self,
        prompt: PromptBundle,
        output_model: type[StrictModel],
    ) -> RuntimeResult:
        provider = provider_for_agent(prompt.agent_id, self.settings)
        started = time.perf_counter()
        budget_error = self._budget_error(prompt)
        if budget_error:
            return _error_result(
                prompt=prompt,
                provider=provider,
                started=started,
                error=budget_error,
            )
        if not provider.api_key_configured:
            return _error_result(
                prompt=prompt,
                provider=provider,
                started=started,
                error=f"Provider {provider.provider} has no API key configured.",
            )
        api_key = _api_key_for_provider(provider.provider, self.settings)
        base_url = (provider.base_url or "").rstrip("/")
        if not base_url or not provider.model_name or not api_key:
            return _error_result(
                prompt=prompt,
                provider=provider,
                started=started,
                error=f"Provider {provider.provider} is missing base_url, model, or api_key.",
            )

        payload = {
            "model": provider.model_name,
            "messages": [
                {"role": "system", "content": prompt.system_prompt},
                {
                    "role": "user",
                    "content": (
                        prompt.user_prompt
                        + "\n\nReturn a single JSON object only. No markdown fences."
                    ),
                },
            ],
            "temperature": 0.2,
            "max_tokens": provider.max_tokens,
            "stream": False,
        }
        if provider.temperature is not None:
            payload["temperature"] = provider.temperature
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(self.settings.p4_llm_max_retries + 1):
            try:
                self.call_count += 1
                response = httpx.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.settings.p4_llm_timeout_seconds,
                )
                response.raise_for_status()
                response_json = response.json()
                content = response_json["choices"][0]["message"]["content"]
                structured_output = _normalize_llm_output(
                    prompt=prompt,
                    output_model=output_model,
                    payload=_parse_json_object(str(content)),
                )
                result = _build_runtime_result(
                    prompt=prompt,
                    provider=provider,
                    output_model=output_model,
                    structured_output=structured_output,
                    started=started,
                    raw_output_ref=f"chat-completions://{provider.provider}/{uuid4().hex[:8]}",
                )
                self.estimated_tokens_used += sum(result.token_usage.values())
                return result
            except Exception as exc:
                last_error = exc
                if attempt >= self.settings.p4_llm_max_retries:
                    break
                time.sleep(min(2.0, 0.4 * (attempt + 1)))
        return _error_result(
            prompt=prompt,
            provider=provider,
            started=started,
            error=(
                "openai_compatible_chat_failed: "
                f"{type(last_error).__name__}: {last_error}"
            ),
        )

    def _budget_error(self, prompt: PromptBundle) -> str | None:
        if self.call_count >= self.settings.p4_llm_max_calls_per_run:
            return "llm_budget_exceeded: max_calls_per_run"
        prompt_tokens = max(1, (len(prompt.system_prompt) + len(prompt.user_prompt)) // 4)
        projected = self.estimated_tokens_used + prompt_tokens
        if projected > self.settings.p4_llm_max_estimated_tokens_per_run:
            return "llm_budget_exceeded: max_estimated_tokens_per_run"
        return None


def provider_for_agent(agent_id: str, settings: Settings | None = None) -> ProviderConfig:
    settings = settings or get_settings()
    provider_name = _provider_name_for_agent(agent_id, settings)
    return provider_config(provider_name, settings)


def provider_config(provider_name: str, settings: Settings | None = None) -> ProviderConfig:
    settings = settings or get_settings()
    provider = provider_name.lower().strip()
    if provider == "openai":
        return _provider_config(
            provider=provider,
            model_name=settings.openai_model,
            base_url=settings.openai_base_url,
            api_key_configured=_secret_configured(settings.openai_api_key),
            settings=settings,
        )
    if provider == "deepseek":
        return _provider_config(
            provider=provider,
            model_name=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            api_key_configured=_secret_configured(settings.deepseek_api_key),
            enable_thinking=settings.deepseek_enable_thinking,
            settings=settings,
        )
    if provider == "qwen":
        return _provider_config(
            provider=provider,
            model_name=settings.qwen_model,
            base_url=settings.qwen_base_url,
            api_key_configured=_secret_configured(settings.qwen_api_key),
            enable_thinking=settings.qwen_enable_thinking,
            settings=settings,
        )
    if provider == "volcano":
        return _provider_config(
            provider=provider,
            model_name=settings.volcano_model,
            base_url=settings.volcano_base_url,
            api_key_configured=_secret_configured(settings.volcano_api_key),
            enable_thinking=settings.volcano_enable_thinking,
            settings=settings,
        )
    if provider == "kimi":
        return _provider_config(
            provider=provider,
            model_name=settings.kimi_model,
            base_url=settings.kimi_base_url,
            api_key_configured=_secret_configured(settings.kimi_api_key),
            enable_thinking=settings.kimi_enable_thinking,
            settings=settings,
        )
    return ProviderConfig(
        provider=provider,
        enabled=False,
        disabled_reason="unknown_provider",
        timeout_seconds=settings.p4_llm_timeout_seconds,
        max_tokens=settings.p4_llm_max_tokens_per_call,
        temperature=settings.p4_llm_temperature,
    )


def _provider_config(
    provider: str,
    model_name: str | None,
    base_url: str | None,
    api_key_configured: bool,
    settings: Settings,
    enable_thinking: bool = False,
) -> ProviderConfig:
    missing: list[str] = []
    if not api_key_configured:
        missing.append("api_key_missing")
    if not base_url:
        missing.append("base_url_missing")
    if not model_name:
        missing.append("model_missing")
    enabled = not missing
    return ProviderConfig(
        provider=provider,
        model_name=model_name,
        base_url=base_url,
        api_key_configured=api_key_configured,
        enabled=enabled,
        disabled_reason=", ".join(missing) if missing else None,
        enable_thinking=enable_thinking,
        timeout_seconds=settings.p4_llm_timeout_seconds,
        max_tokens=settings.p4_llm_max_tokens_per_call,
        temperature=settings.p4_llm_temperature,
    )


def _provider_name_for_agent(agent_id: str, settings: Settings) -> str:
    if agent_id == "macro_event_analyst":
        return settings.p4_macro_event_provider
    if agent_id == "liquidity_flow_analyst":
        return settings.p4_liquidity_flow_provider
    if agent_id == "leverage_microstructure_analyst":
        return settings.p4_leverage_microstructure_provider
    if agent_id == "onchain_market_structure_analyst":
        return settings.p4_onchain_market_structure_provider
    if agent_id == "cross_examiner_agent":
        return settings.p4_cross_exam_provider
    if agent_id == "judge_agent":
        return settings.p4_judge_provider
    if agent_id == "adversarial_reviewer_agent":
        return settings.p4_adversarial_provider
    if agent_id == "article_writer_agent":
        return settings.p4_article_provider
    return settings.p4_article_provider


def _api_key_for_provider(provider_name: str, settings: Settings) -> str | None:
    provider = provider_name.lower().strip()
    if provider == "openai":
        return settings.openai_api_key
    if provider == "deepseek":
        return settings.deepseek_api_key
    if provider == "qwen":
        return settings.qwen_api_key
    if provider == "volcano":
        return settings.volcano_api_key
    if provider == "kimi":
        return settings.kimi_api_key
    return None


def _secret_configured(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    if not normalized:
        return False
    placeholder_markers = ("your_", "placeholder", "changeme", "todo", "example")
    return not any(marker in normalized for marker in placeholder_markers)


def _build_runtime_result(
    prompt: PromptBundle,
    provider: ProviderConfig,
    output_model: type[StrictModel],
    structured_output: dict[str, Any],
    started: float,
    raw_output_ref: str,
    fallback_used: bool = False,
    fallback_reason: str | None = None,
) -> RuntimeResult:
    structured_output = _normalize_llm_output(
        prompt=prompt,
        output_model=output_model,
        payload=structured_output,
    )
    guardrails = _run_guardrails(prompt, output_model, structured_output)
    validated = None
    error = None
    try:
        validated = output_model.model_validate(structured_output).model_dump(mode="json")
    except Exception as exc:
        error = f"structured_output_validation_failed: {type(exc).__name__}: {exc}"
    schema_version = (
        str(validated.get("schema_version"))
        if isinstance(validated, dict) and validated.get("schema_version")
        else None
    )
    failed_guardrails = [item for item in guardrails if not item.passed]
    if failed_guardrails and error is None:
        error = "guardrail_failed: " + "; ".join(
            item.message or item.name for item in failed_guardrails
        )
    return RuntimeResult(
        agent_run_id=f"agent-run-{uuid4().hex[:12]}",
        agent_role=prompt.agent_role,
        agent_name=prompt.agent_id,
        model_provider=provider.provider,
        model_name=provider.model_name,
        prompt_version=prompt.prompt_version,
        schema_version=schema_version,
        trace_id=f"trace-{uuid4().hex[:12]}",
        guardrail_results=guardrails,
        structured_output=validated,
        raw_output_ref=raw_output_ref,
        error=error,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        latency_ms=round((time.perf_counter() - started) * 1000),
        token_usage=_estimate_token_usage(prompt, structured_output),
    )


def _error_result(
    prompt: PromptBundle,
    provider: ProviderConfig,
    started: float,
    error: str,
) -> RuntimeResult:
    return RuntimeResult(
        agent_run_id=f"agent-run-{uuid4().hex[:12]}",
        agent_role=prompt.agent_role,
        agent_name=prompt.agent_id,
        model_provider=provider.provider,
        model_name=provider.model_name,
        prompt_version=prompt.prompt_version,
        schema_version=None,
        trace_id=f"trace-{uuid4().hex[:12]}",
        guardrail_results=[GuardrailResult(name="runtime_available", passed=False, message=error)],
        structured_output=None,
        raw_output_ref=None,
        error=error,
        fallback_used=False,
        fallback_reason=None,
        latency_ms=round((time.perf_counter() - started) * 1000),
    )


def _run_guardrails(
    prompt: PromptBundle,
    output_model: type[StrictModel],
    structured_output: dict[str, Any],
) -> list[GuardrailResult]:
    results = [_schema_guardrail(output_model, structured_output)]
    results.append(_evidence_guardrail(prompt.evidence_ids, structured_output))
    results.append(_trading_advice_guardrail(structured_output))
    return results


def _schema_guardrail(
    output_model: type[StrictModel],
    structured_output: dict[str, Any],
) -> GuardrailResult:
    try:
        output_model.model_validate(structured_output)
    except Exception as exc:
        return GuardrailResult(
            name="structured_output_schema",
            passed=False,
            message=f"{type(exc).__name__}: {exc}",
        )
    return GuardrailResult(name="structured_output_schema", passed=True)


def _evidence_guardrail(
    allowed_evidence_ids: list[str],
    structured_output: dict[str, Any],
) -> GuardrailResult:
    if not allowed_evidence_ids:
        return GuardrailResult(name="evidence_ids_in_pack", passed=True)
    referenced = set(_collect_evidence_ids(structured_output))
    allowed = set(allowed_evidence_ids)
    unknown = sorted(referenced - allowed)
    if unknown:
        return GuardrailResult(
            name="evidence_ids_in_pack",
            passed=False,
            message="Unknown evidence ids: " + ", ".join(unknown),
        )
    if not referenced:
        return GuardrailResult(
            name="evidence_ids_in_pack",
            passed=False,
            message="No evidence_ids referenced in structured output.",
        )
    return GuardrailResult(name="evidence_ids_in_pack", passed=True)


def _trading_advice_guardrail(structured_output: dict[str, Any]) -> GuardrailResult:
    payload = "\n".join(_collect_guardrail_text(structured_output)).lower()
    matched = [term for term in PROHIBITED_TRADING_TERMS if term.lower() in payload]
    if matched:
        return GuardrailResult(
            name="no_trading_advice",
            passed=False,
            message="Prohibited trading terms found: " + ", ".join(matched),
        )
    return GuardrailResult(name="no_trading_advice", passed=True)


def _collect_guardrail_text(value: Any, parent_key: str | None = None) -> list[str]:
    free_text_keys = {
        "claim",
        "uncertainty",
        "missing_evidence",
        "risk_flags",
        "publish_constraints",
        "reason",
        "accepted_points",
        "rejected_points",
        "findings",
        "required_fixes",
        "dominant_drivers",
        "invalidation_watch",
        "observation_points",
        "data_quality_notes",
        "blocked_by",
        "title",
        "summary",
        "heading",
        "body",
        "note",
        "history_references",
        "state_constraints",
        "trend_insight",
        "marginal_change",
        "sensitive_signals",
        "early_warning_signals",
        "conflict_weighting",
        "scenario_map",
        "invalidation_conditions",
        "watch_horizon",
        "confidence_explanation",
        "audit_constraints_summary",
    }
    if isinstance(value, dict):
        text: list[str] = []
        for key, item in value.items():
            text.extend(_collect_guardrail_text(item, key))
        return text
    if isinstance(value, list):
        text: list[str] = []
        for item in value:
            text.extend(_collect_guardrail_text(item, parent_key))
        return text
    if isinstance(value, str) and parent_key in free_text_keys:
        return [value]
    return []


def _collect_evidence_ids(value: Any) -> list[str]:
    ids: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "evidence_ids" and isinstance(item, list):
                ids.extend(str(evidence_id) for evidence_id in item)
            elif key == "evidence_id" and isinstance(item, str):
                ids.append(item)
            else:
                ids.extend(_collect_evidence_ids(item))
    elif isinstance(value, list):
        for item in value:
            ids.extend(_collect_evidence_ids(item))
    return ids


def _estimate_token_usage(
    prompt: PromptBundle,
    structured_output: dict[str, Any],
) -> dict[str, int]:
    prompt_chars = len(prompt.system_prompt) + len(prompt.user_prompt)
    output_chars = len(json.dumps(structured_output, ensure_ascii=False))
    return {
        "prompt_tokens_estimated": max(1, prompt_chars // 4),
        "completion_tokens_estimated": max(1, output_chars // 4),
    }


def _normalize_llm_output(
    prompt: PromptBundle,
    output_model: type[StrictModel],
    payload: dict[str, Any],
) -> dict[str, Any]:
    payload = _unwrap_model_payload(output_model, payload)
    if output_model is CrossExamChallenge:
        return _repair_cross_exam_challenge(prompt, payload)
    if output_model is CrossExamRevision:
        return _repair_cross_exam_revision(prompt, payload)
    if output_model is JudgeSynthesis:
        return _filter_schema_fields(output_model, payload)
    if output_model not in {AnalystReadableArticle, FinalObservationArticle}:
        return payload
    payload = _repair_article_payload(prompt, output_model, payload)
    payload = _sanitize_article_trading_terms(payload)
    fallback_id = prompt.evidence_ids[0] if prompt.evidence_ids else "mock-evidence"
    for section in payload.get("sections") or []:
        if isinstance(section, dict) and not section.get("evidence_ids"):
            section["evidence_ids"] = [fallback_id]
    if not payload.get("evidence_citations"):
        payload["evidence_citations"] = [
            {
                "evidence_id": fallback_id,
                "note": "Runtime filled missing citation from allowed evidence ids.",
            }
        ]
    return payload


def _filter_schema_fields(
    output_model: type[StrictModel],
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key in output_model.model_fields}


def _repair_cross_exam_challenge(prompt: PromptBundle, payload: dict[str, Any]) -> dict[str, Any]:
    context = _extract_prompt_json(prompt.user_prompt)
    candidate = (
        context.get("candidate_challenge")
        if isinstance(context.get("candidate_challenge"), dict)
        else {}
    )
    challenge_type = str(
        payload.get("challenge_type") or candidate.get("challenge_type") or "missing_evidence"
    )
    if challenge_type not in {
        "missing_evidence",
        "evidence_conflict",
        "data_quality",
        "overreach",
        "ignored_invalidation",
        "history_drift",
    }:
        challenge_type = "missing_evidence"
    evidence_ids = _safe_prompt_evidence_ids(
        _filter_allowed_evidence_ids(payload.get("evidence_ids"), prompt.evidence_ids),
        candidate.get("evidence_ids"),
        prompt.evidence_ids,
    )
    return {
        "schema_version": "p4.cross_exam_challenge.v1",
        "challenge_id": str(
            payload.get("challenge_id")
            or candidate.get("challenge_id")
            or f"challenge-{uuid4().hex[:8]}"
        ),
        "from_agent": str(
            payload.get("from_agent") or candidate.get("from_agent") or prompt.agent_id
        ),
        "to_agent": str(
            payload.get("to_agent") or candidate.get("to_agent") or "macro_event_analyst"
        ),
        "challenge_type": challenge_type,
        "claim_under_review": str(
            payload.get("claim_under_review")
            or payload.get("claim")
            or candidate.get("claim_under_review")
            or "Cross-exam challenge repaired from LLM output."
        ),
        "evidence_ids": evidence_ids,
        "severity": str(payload.get("severity") or candidate.get("severity") or "medium"),
        "required_response": str(
            payload.get("required_response")
            or candidate.get("required_response")
            or "Respond with evidence-backed vote/confidence review."
        ),
    }


def _repair_cross_exam_revision(prompt: PromptBundle, payload: dict[str, Any]) -> dict[str, Any]:
    context = _extract_prompt_json(prompt.user_prompt)
    challenge = context.get("challenge") if isinstance(context.get("challenge"), dict) else {}
    vote = context.get("vote") if isinstance(context.get("vote"), dict) else {}
    evidence_ids = _safe_prompt_evidence_ids(
        payload.get("evidence_ids"),
        challenge.get("evidence_ids"),
        vote.get("evidence_ids"),
        prompt.evidence_ids,
    )
    previous_vote = _safe_vote(vote.get("vote"), payload.get("previous_vote"))
    previous_confidence = _safe_float(
        vote.get("confidence"),
        payload.get("previous_confidence"),
        default=0.5,
    )
    revised_vote = _safe_vote(payload.get("revised_vote"), payload.get("vote"), previous_vote)
    revised_confidence = _safe_float(
        payload.get("revised_confidence"),
        payload.get("confidence"),
        previous_confidence,
        default=previous_confidence,
    )
    changed = payload.get("changed")
    if not isinstance(changed, bool):
        changed = revised_vote != previous_vote or revised_confidence != previous_confidence
    repaired = {
        "schema_version": "p4.cross_exam_revision.v1",
        "challenge_id": str(
            payload.get("challenge_id")
            or challenge.get("challenge_id")
            or f"challenge-{uuid4().hex[:8]}"
        ),
        "responding_agent": str(
            payload.get("responding_agent")
            or vote.get("model_name")
            or challenge.get("to_agent")
            or prompt.agent_id
        ),
        "changed": changed,
        "previous_vote": previous_vote,
        "revised_vote": revised_vote,
        "previous_confidence": previous_confidence,
        "revised_confidence": revised_confidence,
        "accepted_points": _safe_string_list(payload.get("accepted_points")),
        "rejected_points": _safe_string_list(payload.get("rejected_points")),
        "reason": str(
            payload.get("reason")
            or payload.get("rationale")
            or "Schema repair merged LLM revision with fallback vote context."
        ),
        "evidence_ids": evidence_ids,
    }
    if not repaired["accepted_points"] and changed:
        repaired["accepted_points"] = [
            "LLM revision changed vote or confidence after challenge review."
        ]
    if not repaired["rejected_points"] and not changed:
        repaired["rejected_points"] = [
            "No change after repair; original evidence still supports scoped conclusion."
        ]
    return repaired


def _repair_article_payload(
    prompt: PromptBundle,
    output_model: type[StrictModel],
    payload: dict[str, Any],
) -> dict[str, Any]:
    fallback_id = prompt.evidence_ids[0] if prompt.evidence_ids else "mock-evidence"
    if output_model is AnalystReadableArticle:
        analyst_id = (
            _extract_prompt_value(prompt.user_prompt, "analyst_id")
            or payload.get("analyst_id")
            or "macro_event_analyst"
        )
        payload = _wrap_partial_article_payload(
            payload=payload,
            title="分析师研究要点",
            summary="LLM returned partial article content; runtime repaired it into schema.",
            evidence_id=fallback_id,
        )
        payload.setdefault("schema_version", "p4.analyst_readable_article.v1")
        payload.setdefault("analyst_id", analyst_id)
        payload.setdefault("headline", payload.get("title"))
        payload.setdefault("core_view", payload.get("summary"))
        payload.setdefault("key_drivers", [])
        payload.setdefault("counter_evidence", [])
        payload.setdefault("watch_items", [])
        payload.setdefault("confidence_rationale", "Runtime schema repair applied.")
    elif output_model is FinalObservationArticle:
        payload = _wrap_partial_article_payload(
            payload=payload,
            title="最终观察文章",
            summary="LLM returned partial final article content; runtime repaired it into schema.",
            evidence_id=fallback_id,
        )
        payload.setdefault("schema_version", "p4.final_observation_article.v1")
        payload.setdefault("executive_summary", payload.get("summary"))
        payload.setdefault("market_state", payload.get("summary"))
        payload.setdefault("driver_analysis", "")
        payload.setdefault("conflict_analysis", "")
        payload.setdefault("history_delta", "")
        payload.setdefault("event_watch", "")
        payload.setdefault("quality_and_runtime", "")
        payload.setdefault("final_observation", payload.get("summary"))
    payload.setdefault("history_references", [])
    payload.setdefault("state_constraints", [])
    payload.setdefault("data_quality_notes", [])
    if output_model is FinalObservationArticle:
        payload.setdefault("analyst_article_titles", [])
        payload.setdefault("publish_constraints", [])
    if not payload.get("data_source_appendix"):
        payload["data_source_appendix"] = payload.get("evidence_citations") or [
            {
                "evidence_id": fallback_id,
                "note": "Runtime filled data source appendix from allowed evidence ids.",
            }
        ]
    return payload


def _wrap_partial_article_payload(
    payload: dict[str, Any],
    title: str,
    summary: str,
    evidence_id: str,
) -> dict[str, Any]:
    if payload.get("title") and payload.get("summary") and payload.get("sections"):
        return payload
    if payload.get("heading") or payload.get("body"):
        section = {
            "heading": str(payload.get("heading") or title),
            "body": str(payload.get("body") or payload.get("summary") or summary),
            "evidence_ids": payload.get("evidence_ids") or [evidence_id],
        }
        cleaned = {
            key: value
            for key, value in payload.items()
            if key not in {"heading", "body", "evidence_ids"}
        }
        return {
            **cleaned,
            "title": str(payload.get("title") or section["heading"]),
            "summary": str(payload.get("summary") or section["body"]),
            "sections": [section],
        }
    if isinstance(payload.get("sections"), list) and payload["sections"]:
        first = payload["sections"][0]
        if isinstance(first, dict):
            return {
                **payload,
                "title": str(payload.get("title") or first.get("heading") or title),
                "summary": str(payload.get("summary") or first.get("body") or summary),
            }
    return {
        **payload,
        "title": str(payload.get("title") or title),
        "summary": str(payload.get("summary") or summary),
        "sections": payload.get("sections")
        or [{"heading": title, "body": summary, "evidence_ids": [evidence_id]}],
    }


def _sanitize_article_trading_terms(payload: dict[str, Any]) -> dict[str, Any]:
    return payload


def _extract_prompt_json(text: str) -> dict[str, Any]:
    try:
        return _extract_embedded_json_object(text)
    except ValueError:
        return {}


def _safe_prompt_evidence_ids(*groups: Any) -> list[str]:
    evidence_ids: list[str] = []
    for group in groups:
        if isinstance(group, list):
            evidence_ids.extend(str(item) for item in group if item)
    return sorted(set(evidence_ids))[:20] or ["no-evidence-id-available"]


def _filter_allowed_evidence_ids(value: Any, allowed: list[str]) -> list[str]:
    if not isinstance(value, list):
        return []
    allowed_set = set(allowed)
    return [str(item) for item in value if str(item) in allowed_set]


def _safe_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def _safe_vote(*values: Any) -> str:
    allowed = {"bullish", "bearish", "neutral", "mixed", "risk_off", "insufficient_evidence"}
    for value in values:
        if isinstance(value, str) and value in allowed:
            return value
        if isinstance(value, dict):
            nested = value.get("vote") or value.get("revised_vote") or value.get("previous_vote")
            if isinstance(nested, str) and nested in allowed:
                return nested
    return "neutral"


def _safe_float(*values: Any, default: float) -> float:
    for value in values:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        return max(0.0, min(1.0, parsed))
    return default


def _unwrap_model_payload(
    output_model: type[StrictModel],
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    wrapper_keys: dict[type[StrictModel], tuple[str, ...]] = {
        AnalystOutput: ("analyst_output", "output", "result"),
        CrossExamChallenge: (
            "candidate_challenge",
            "cross_exam_challenge",
            "challenge",
            "output",
            "result",
        ),
        CrossExamRevision: ("cross_exam_revision", "revision", "output", "result"),
        JudgeSynthesis: ("judge_synthesis", "synthesis", "output", "result"),
        AdversarialReview: ("adversarial_review", "review", "output", "result"),
        AnalystReadableArticle: ("analyst_readable_article", "article", "output", "result"),
        FinalObservationArticle: ("final_observation_article", "article", "output", "result"),
    }
    for key in wrapper_keys.get(output_model, ()):
        nested = payload.get(key)
        if isinstance(nested, dict):
            return nested
    return payload


def _parse_json_object(content: str) -> dict[str, Any]:
    stripped = _strip_json_fences(content)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = _extract_embedded_json_object(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object")
    return parsed


def _extract_embedded_json_object(content: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(content):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(content[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("No JSON object found in LLM response")


def _mock_output(
    prompt: PromptBundle,
    output_model: type[StrictModel],
) -> dict[str, Any]:
    evidence_id = prompt.evidence_ids[0] if prompt.evidence_ids else "mock-evidence"
    if output_model is AnalystOutput:
        return {
            "analyst_id": prompt.agent_id,
            "vote": "neutral",
            "confidence": 0.5,
            "confidence_discount": 0.1,
            "time_horizon": "1-5d",
            "key_claims": [
                {
                    "claim": "Mock analyst output is constrained to provided evidence.",
                    "evidence_ids": [evidence_id],
                    "direction": "neutral",
                    "strength": 0.4,
                    "uncertainty": "mock runtime",
                }
            ],
            "conflicting_evidence": [],
            "missing_evidence": [],
            "risk_flags": [],
            "publish_constraints": [],
            "history_delta": {"changed": False, "previous_vote": None, "reason": "mock runtime"},
        }
    if output_model is CrossExamChallenge:
        return {
            "challenge_id": f"challenge-{uuid4().hex[:8]}",
            "from_agent": "cross_examiner_agent",
            "to_agent": "macro_event_analyst",
            "challenge_type": "missing_evidence",
            "claim_under_review": "Mock challenge checks evidence sufficiency.",
            "evidence_ids": [evidence_id],
            "severity": "low",
            "required_response": "Confirm whether evidence is sufficient.",
        }
    if output_model is JudgeSynthesis:
        return {
            "judge_synthesis_id": f"judge-{uuid4().hex[:8]}",
            "debate_id": "mock-debate",
            "pack_id": "mock-pack",
            "controller_run_id": "mock-run",
            "dominant_regime": "neutral",
            "trend_state": "neutral",
            "risk_state": "watch",
            "consensus_level": "low",
            "disagreement_level": "low",
            "accepted_claims": [],
            "rejected_claims": [],
            "minority_objections": [],
            "confidence": 0.5,
            "confidence_discount": 0.1,
            "blocked_by": [],
            "publish_allowed": True,
            "evidence_ids": [evidence_id],
            "state_machine_constraints_applied": [],
        }
    if output_model is AdversarialReview:
        return {
            "review_id": f"review-{uuid4().hex[:8]}",
            "judge_synthesis_id": "mock-judge",
            "passed": True,
            "publish_allowed": True,
            "findings": [],
            "required_fixes": [],
            "evidence_ids": [evidence_id],
        }
    if output_model is AnalystReadableArticle:
        analyst_id = (
            _extract_prompt_value(prompt.user_prompt, "analyst_id")
            or "macro_event_analyst"
        )
        return {
            "analyst_id": analyst_id,
            "title": "模拟分析师中文审计结论",
            "summary": f"本段为稳定测试输出，结论仅引用证据 {evidence_id}。",
            "sections": [
                {
                    "heading": "核心观察",
                    "body": f"当前证据集中，{evidence_id} 是本分析师结论的主要依据。",
                    "evidence_ids": [evidence_id],
                }
            ],
            "evidence_citations": [
                {
                    "evidence_id": evidence_id,
                    "metric_id": None,
                    "source_id": None,
                    "value": None,
                    "quality_score": None,
                    "note": "模拟文章引用的证据。",
                }
            ],
            "history_references": ["mock runtime history continuity"],
            "state_constraints": [],
            "data_quality_notes": [],
        }
    if output_model is FinalObservationArticle:
        return {
            "title": "模拟最终观察文章",
            "summary": f"本段为稳定测试输出，最终观察引用证据 {evidence_id}。",
            "sections": [
                {
                    "heading": "综合结论",
                    "body": f"最终观察保留状态机和审计约束，并回链到 {evidence_id}。",
                    "evidence_ids": [evidence_id],
                }
            ],
            "evidence_citations": [
                {
                    "evidence_id": evidence_id,
                    "metric_id": None,
                    "source_id": None,
                    "value": None,
                    "quality_score": None,
                    "note": "模拟最终文章引用的证据。",
                }
            ],
            "analyst_article_titles": ["模拟分析师中文审计结论"],
            "history_references": ["mock runtime history continuity"],
            "state_constraints": [],
            "data_quality_notes": [],
            "publish_constraints": [],
        }
    raise ValueError(f"No mock output factory for {output_model.__name__}")


def _strip_json_fences(content: str) -> str:
    stripped = content.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return stripped


def _extract_prompt_value(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()
