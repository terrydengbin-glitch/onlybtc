from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select

from onlybtc.core.config import Settings, get_settings
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p4.agent_runtime import provider_config
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID

P45_LLM_ANALYST_ARTICLES_MODULE_ID = "p45_llm_analyst_articles"
P45_LLM_ANALYST_ARTICLES_SCHEMA_VERSION = "p45.llm_analyst_articles.v1"

ANALYST_NAMES = {
    "macro_event_analyst": "宏观与事件分析师",
    "liquidity_flow_analyst": "流动性与资金流分析师",
    "microstructure_analyst": "微观结构分析师",
    "onchain_structure_analyst": "链上结构分析师",
}


def run_p45_llm_analyst_writers(
    pack_id: str | None = None,
    analyst_run_id: str | None = None,
    runtime_mode: str = "llm",
    provider_name: str | None = None,
    db: Database = database,
    settings: Settings | None = None,
) -> dict[str, Any]:
    db.init_schema()
    settings = settings or get_settings()
    with db.session() as session:
        pack_payload = _load_pack(session, pack_id)
        if pack_payload is None:
            raise RuntimeError("P4.5 evidence pack payload is missing.")
        analyst_run_id = analyst_run_id or _generate_analyst_run_id()
        provider = provider_name or settings.p45_research_provider
        articles = [
            _run_one_analyst(
                analyst=analyst,
                pack_payload=pack_payload,
                analyst_run_id=analyst_run_id,
                runtime_mode=runtime_mode,
                provider_name=provider,
                settings=settings,
            )
            for analyst in pack_payload.get("analysts", [])
        ]
        result = {
            "schema_version": P45_LLM_ANALYST_ARTICLES_SCHEMA_VERSION,
            "llm_analyst_run_id": analyst_run_id,
            "pack_id": pack_payload.get("pack_id"),
            "p3_run_id": pack_payload.get("p3_run_id"),
            "p2_radar_run_id": pack_payload.get("p2_radar_run_id"),
            "collect_run_id": pack_payload.get("collect_run_id"),
            "runtime_mode": runtime_mode,
            "provider": provider,
            "created_at": datetime.now(UTC).isoformat(),
            "analyst_articles": articles,
            "summary": {
                "analyst_count": len(articles),
                "completed_count": sum(1 for item in articles if item["status"] == "completed"),
                "failed_count": sum(1 for item in articles if item["status"] == "failed"),
                "radar_modules_covered": sorted(
                    {
                        module
                        for item in articles
                        for module in item.get("radar_modules_covered", [])
                    }
                ),
                "evidence_ids_used_count": len(
                    {
                        evidence_id
                        for item in articles
                        for evidence_id in item.get("evidence_ids_used", [])
                    }
                ),
            },
        }
        session.add(
            schema.ModuleJsonOutput(
                run_id=analyst_run_id,
                module_id=P45_LLM_ANALYST_ARTICLES_MODULE_ID,
                schema_version=P45_LLM_ANALYST_ARTICLES_SCHEMA_VERSION,
                payload=result,
            )
        )
        return result


def _run_one_analyst(
    analyst: dict[str, Any],
    pack_payload: dict[str, Any],
    analyst_run_id: str,
    runtime_mode: str,
    provider_name: str,
    settings: Settings,
) -> dict[str, Any]:
    started = time.perf_counter()
    context = _analyst_context(analyst, pack_payload)
    provider = provider_config(provider_name, settings)
    if runtime_mode == "mock":
        output = _mock_output(context)
        return _article_payload(
            analyst_run_id=analyst_run_id,
            status="completed",
            runtime_mode=runtime_mode,
            provider=provider.provider,
            model=provider.model_name,
            context=context,
            output=output,
            latency_ms=_latency_ms(started),
            error=None,
        )
    if runtime_mode != "llm":
        return _failed_article(
            analyst_run_id=analyst_run_id,
            runtime_mode=runtime_mode,
            provider=provider.provider,
            model=provider.model_name,
            context=context,
            started=started,
            error=f"Unsupported runtime_mode: {runtime_mode}",
        )
    if not provider.api_key_configured:
        return _failed_article(
            analyst_run_id=analyst_run_id,
            runtime_mode=runtime_mode,
            provider=provider.provider,
            model=provider.model_name,
            context=context,
            started=started,
            error=f"Provider {provider.provider} has no API key configured.",
        )
    api_key = _api_key_for_provider(provider.provider, settings)
    if not provider.base_url or not provider.model_name or not api_key:
        return _failed_article(
            analyst_run_id=analyst_run_id,
            runtime_mode=runtime_mode,
            provider=provider.provider,
            model=provider.model_name,
            context=context,
            started=started,
            error=f"Provider {provider.provider} is missing base_url, model, or api_key.",
        )
    error = ""
    for attempt in range(settings.p45_research_max_retries + 1):
        try:
            response = httpx.post(
                f"{provider.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": provider.model_name,
                    "messages": [
                        {"role": "system", "content": _system_prompt()},
                        {"role": "user", "content": _user_prompt(context)},
                    ],
                    "temperature": 0.25,
                    "stream": False,
                },
                timeout=settings.p45_research_timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            output = _repair_output(_parse_json_object(str(content)), context)
            validation_error = _validate_output(output, context)
            if validation_error:
                raise ValueError(validation_error)
            return _article_payload(
                analyst_run_id=analyst_run_id,
                status="completed",
                runtime_mode=runtime_mode,
                provider=provider.provider,
                model=provider.model_name,
                context=context,
                output=output,
                latency_ms=_latency_ms(started),
                error=None,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if attempt >= settings.p45_research_max_retries:
                break
            time.sleep(min(2.0, 0.4 * (attempt + 1)))
    return _failed_article(
        analyst_run_id=analyst_run_id,
        runtime_mode=runtime_mode,
        provider=provider.provider,
        model=provider.model_name,
        context=context,
        started=started,
        error=f"llm_analyst_writer_failed: {error}",
    )


def _article_payload(
    analyst_run_id: str,
    status: str,
    runtime_mode: str,
    provider: str,
    model: str | None,
    context: dict[str, Any],
    output: dict[str, Any],
    latency_ms: int,
    error: str | None,
) -> dict[str, Any]:
    return {
        "llm_analyst_run_id": analyst_run_id,
        "analyst_id": context["analyst_id"],
        "title": output.get("title") or f"{context['analyst_name']} LLM 板块深度分析",
        "runtime_mode": runtime_mode,
        "provider": provider,
        "model": model,
        "status": status,
        "article": output.get("article", ""),
        "radar_modules_covered": output.get("radar_modules_covered", []),
        "evidence_ids_used": output.get("evidence_ids_used", []),
        "metric_evidence_count_seen": len(context["metric_evidence"]),
        "module_count_seen": len(context["radar_modules"]),
        "latency_ms": latency_ms,
        "error": error,
    }


def _failed_article(
    analyst_run_id: str,
    runtime_mode: str,
    provider: str,
    model: str | None,
    context: dict[str, Any],
    started: float,
    error: str,
) -> dict[str, Any]:
    return _article_payload(
        analyst_run_id=analyst_run_id,
        status="failed",
        runtime_mode=runtime_mode,
        provider=provider,
        model=model,
        context=context,
        output={
            "title": f"{context['analyst_name']} LLM 板块深度分析",
            "article": "",
            "radar_modules_covered": [],
            "evidence_ids_used": [],
        },
        latency_ms=_latency_ms(started),
        error=error,
    )


def _analyst_context(
    analyst: dict[str, Any],
    pack_payload: dict[str, Any],
) -> dict[str, Any]:
    modules = []
    metrics = []
    for module in analyst.get("modules", []):
        modules.append(
            {
                "radar_module": module.get("radar_module"),
                "module_score": module.get("module_score"),
                "module_direction": module.get("module_direction"),
                "module_strength": module.get("module_strength"),
                "module_confidence": module.get("module_confidence"),
                "module_quality_score": module.get("module_quality_score"),
                "positive_metric_count": module.get("positive_metric_count"),
                "negative_metric_count": module.get("negative_metric_count"),
                "zero_metric_count": module.get("zero_metric_count"),
                "unavailable_metric_count": module.get("unavailable_metric_count"),
                "module_explanation": module.get("module_explanation"),
                "data_boundary": module.get("data_boundary"),
            }
        )
        for metric in module.get("metrics", []):
            metrics.append(
                {
                    "evidence_id": metric.get("evidence_id"),
                    "radar_module": module.get("radar_module"),
                    "metric_id": metric.get("metric_id"),
                    "source_id": metric.get("source_id"),
                    "value": metric.get("value"),
                    "metric_score": metric.get("metric_score"),
                    "base_metric_score": metric.get("base_metric_score"),
                    "score_bucket": metric.get("score_bucket"),
                    "direction": metric.get("direction"),
                    "base_direction": metric.get("base_direction"),
                    "quality_score": metric.get("quality_score"),
                    "semantic_rule_id": metric.get("semantic_rule_id"),
                    "semantic_warning": metric.get("semantic_warning"),
                    "p45_metric_brief": metric.get("p45_metric_brief"),
                    "score_reason": metric.get("score_reason"),
                }
            )
    analyst_id = analyst.get("analyst_id")
    return {
        "analyst_id": analyst_id,
        "analyst_name": ANALYST_NAMES.get(str(analyst_id), str(analyst_id)),
        "pack_id": pack_payload.get("pack_id"),
        "p3_run_id": pack_payload.get("p3_run_id"),
        "radar_modules": modules,
        "metric_evidence": metrics,
        "summary": {
            "module_count": len(modules),
            "metric_evidence_count": len(metrics),
            "positive": _count_bucket(metrics, "positive"),
            "negative": _count_bucket(metrics, "negative"),
            "zero": _count_bucket(metrics, "zero"),
            "unavailable": _count_bucket(metrics, "unavailable"),
        },
    }


def _system_prompt() -> str:
    return (
        "你是 onlyBTC 的 P4.5 专业分析师。你只能分析输入 JSON 中属于自己的 "
        "Radar modules 和 evidence，不允许跨板块引用。不要给交易指令。"
        "必须输出单个 JSON object，不要 markdown fence。"
    )


def _user_prompt(context: dict[str, Any]) -> str:
    return (
        f"请作为{context['analyst_name']}，基于自己的 evidence slice 写一篇中文板块深度分析。\n"
        "要求：\n"
        "1. 必须引用 evidence_id、指标值、metric_score、module_score。\n"
        "2. 必须解释核心结论、正向证据、负向证据、零分观察项、unavailable 数据边界。\n"
        "3. 必须给出 24h / 3d / 7d 观察路径。\n"
        "4. 不得引用自己 slice 之外的 evidence。\n"
        "5. 输出 JSON schema：\n"
        "{\n"
        '  "title": "string",\n'
        '  "article": "markdown text",\n'
        '  "evidence_ids_used": ["..."],\n'
        '  "radar_modules_covered": ["..."]\n'
        "}\n\n"
        "Analyst context JSON:\n"
        + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    )


def _mock_output(context: dict[str, Any]) -> dict[str, Any]:
    modules = context["radar_modules"]
    metrics = context["metric_evidence"]
    positives = [item for item in metrics if item.get("score_bucket") == "positive"]
    negatives = [item for item in metrics if item.get("score_bucket") == "negative"]
    zero = [item for item in metrics if item.get("score_bucket") == "zero"]
    unavailable = [item for item in metrics if item.get("score_bucket") == "unavailable"]
    evidence_ids = [
        str(item["evidence_id"])
        for item in [*positives[:4], *negatives[:4], *zero[:2], *unavailable[:2]]
        if item.get("evidence_id")
    ]
    article = "\n\n".join(
        [
            f"# {context['analyst_name']} LLM 板块深度分析（Mock）",
            (
                f"本分析师覆盖 {len(modules)} 个 Radar module、{len(metrics)} 条 evidence。"
                f"正分 {context['summary']['positive']}，负分 {context['summary']['negative']}，"
                f"零分 {context['summary']['zero']}，不可用 {context['summary']['unavailable']}。"
            ),
            "## 模块结论\n" + "\n".join(_module_line(item) for item in modules),
            "## 正向证据\n" + _metric_lines(positives[:4]),
            "## 负向证据\n" + _metric_lines(negatives[:4]),
            "## 中性与数据边界\n" + _metric_lines([*zero[:3], *unavailable[:3]]),
            "## 观察路径\n24h 看边际变化；3d 看信号是否扩散；7d 看模块间是否共振。",
        ]
    )
    return {
        "title": f"{context['analyst_name']} LLM 板块深度分析（Mock）",
        "article": article,
        "evidence_ids_used": evidence_ids,
        "radar_modules_covered": [item["radar_module"] for item in modules],
    }


def _module_line(item: dict[str, Any]) -> str:
    return (
        f"- {item.get('radar_module')} module_score={item.get('module_score')}，"
        f"方向={item.get('module_direction')}，{item.get('module_explanation')}"
    )


def _metric_lines(items: list[dict[str, Any]]) -> str:
    if not items:
        return "无。"
    return "\n".join(
        (
            f"- {item.get('metric_id')} value={item.get('value')} "
            f"metric_score={item.get('metric_score')} evidence_id={item.get('evidence_id')}，"
            f"{item.get('p45_metric_brief') or item.get('score_reason')}"
        )
        for item in items
    )


def _repair_output(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    allowed_ids = {str(item.get("evidence_id")) for item in context["metric_evidence"]}
    allowed_ids.discard("None")
    allowed_modules = {str(item.get("radar_module")) for item in context["radar_modules"]}
    article = str(payload.get("article") or "")
    evidence_ids = [
        str(item)
        for item in payload.get("evidence_ids_used", [])
        if str(item) in allowed_ids
    ]
    if not evidence_ids:
        evidence_ids = sorted(
            evidence_id for evidence_id in allowed_ids if evidence_id in article
        )
    modules = [
        str(item)
        for item in payload.get("radar_modules_covered", [])
        if str(item) in allowed_modules
    ]
    return {
        "title": str(payload.get("title") or f"{context['analyst_name']} LLM 板块深度分析"),
        "article": article,
        "evidence_ids_used": evidence_ids,
        "radar_modules_covered": modules,
    }


def _validate_output(payload: dict[str, Any], context: dict[str, Any]) -> str | None:
    if len(str(payload.get("article") or "")) < 500:
        return "article_too_short"
    if not payload.get("evidence_ids_used"):
        return "missing_evidence_ids_used"
    expected_modules = {item["radar_module"] for item in context["radar_modules"]}
    covered = set(payload.get("radar_modules_covered") or [])
    missing = sorted(expected_modules - covered)
    if missing:
        return "missing_radar_modules_covered: " + ", ".join(missing)
    return None


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("LLM output is not a JSON object.")
    return value


def _load_pack(session, pack_id: str | None) -> dict[str, Any] | None:
    query = select(schema.ModuleJsonOutput).where(
        schema.ModuleJsonOutput.module_id == P45_EVIDENCE_PACK_MODULE_ID
    )
    if pack_id:
        query = query.where(schema.ModuleJsonOutput.run_id == pack_id)
    row = session.scalar(query.order_by(schema.ModuleJsonOutput.created_at.desc()).limit(1))
    return dict(row.payload) if row else None


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


def _count_bucket(items: list[dict[str, Any]], bucket: str) -> int:
    return sum(1 for item in items if item.get("score_bucket") == bucket)


def _latency_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _generate_analyst_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"p45llmanalysts-{stamp}-{uuid4().hex[:6]}"
