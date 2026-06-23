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
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID
from onlybtc.p45.writer import P45_ANALYST_ARTICLES_MODULE_ID

P45_LLM_RESEARCH_ARTICLE_MODULE_ID = "p45_llm_research_article"
P45_LLM_RESEARCH_ARTICLE_SCHEMA_VERSION = "p45.llm_research_article.v1"


def run_p45_llm_research_writer(
    final_run_id: str | None = None,
    research_run_id: str | None = None,
    runtime_mode: str = "llm",
    provider_name: str | None = None,
    db: Database = database,
    settings: Settings | None = None,
) -> dict[str, Any]:
    db.init_schema()
    settings = settings or get_settings()
    with db.session() as session:
        final_payload = _load_payload(
            session=session,
            module_id=P45_FINAL_ARTICLE_MODULE_ID,
            run_id=final_run_id,
        )
        if final_payload is None:
            raise RuntimeError("P4.5 final article payload is missing.")
        article_payload = _load_payload(
            session=session,
            module_id=P45_ANALYST_ARTICLES_MODULE_ID,
            run_id=final_payload.get("article_run_id"),
        )
        pack_payload = _load_payload(
            session=session,
            module_id=P45_EVIDENCE_PACK_MODULE_ID,
            run_id=final_payload.get("pack_id"),
        )
        if article_payload is None:
            raise RuntimeError("P4.5 analyst article payload is missing.")
        if pack_payload is None:
            raise RuntimeError("P4.5 evidence pack payload is missing.")

        research_run_id = research_run_id or _generate_research_run_id()
        result = _run_writer(
            research_run_id=research_run_id,
            runtime_mode=runtime_mode,
            provider_name=provider_name or settings.p45_research_provider,
            final_payload=final_payload,
            article_payload=article_payload,
            pack_payload=pack_payload,
            settings=settings,
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id=research_run_id,
                module_id=P45_LLM_RESEARCH_ARTICLE_MODULE_ID,
                schema_version=P45_LLM_RESEARCH_ARTICLE_SCHEMA_VERSION,
                payload=result,
            )
        )
        return result


def _run_writer(
    research_run_id: str,
    runtime_mode: str,
    provider_name: str,
    final_payload: dict[str, Any],
    article_payload: dict[str, Any],
    pack_payload: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    started = time.perf_counter()
    context = _research_context(final_payload, article_payload, pack_payload)
    provider = provider_config(provider_name, settings)
    if runtime_mode == "mock":
        output = _mock_article(context)
        return _payload(
            research_run_id=research_run_id,
            status="completed",
            runtime_mode=runtime_mode,
            provider=provider.provider,
            model=provider.model_name,
            final_payload=final_payload,
            output=output,
            context=context,
            latency_ms=_latency_ms(started),
        )
    if runtime_mode != "llm":
        return _failed_payload(
            research_run_id=research_run_id,
            runtime_mode=runtime_mode,
            provider=provider.provider,
            model=provider.model_name,
            final_payload=final_payload,
            context=context,
            started=started,
            error=f"Unsupported runtime_mode: {runtime_mode}",
        )
    if not provider.api_key_configured:
        return _failed_payload(
            research_run_id=research_run_id,
            runtime_mode=runtime_mode,
            provider=provider.provider,
            model=provider.model_name,
            final_payload=final_payload,
            context=context,
            started=started,
            error=f"Provider {provider.provider} has no API key configured.",
        )
    api_key = _api_key_for_provider(provider.provider, settings)
    if not provider.base_url or not provider.model_name or not api_key:
        return _failed_payload(
            research_run_id=research_run_id,
            runtime_mode=runtime_mode,
            provider=provider.provider,
            model=provider.model_name,
            final_payload=final_payload,
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
            status = _validate_output(output, context)
            if status:
                raise ValueError(status)
            return _payload(
                research_run_id=research_run_id,
                status="completed",
                runtime_mode=runtime_mode,
                provider=provider.provider,
                model=provider.model_name,
                final_payload=final_payload,
                output=output,
                context=context,
                latency_ms=_latency_ms(started),
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if attempt >= settings.p45_research_max_retries:
                break
            time.sleep(min(2.0, 0.4 * (attempt + 1)))
    return _failed_payload(
        research_run_id=research_run_id,
        runtime_mode=runtime_mode,
        provider=provider.provider,
        model=provider.model_name,
        final_payload=final_payload,
        context=context,
        started=started,
        error=f"llm_research_writer_failed: {error}",
    )


def _payload(
    research_run_id: str,
    status: str,
    runtime_mode: str,
    provider: str,
    model: str | None,
    final_payload: dict[str, Any],
    output: dict[str, Any],
    context: dict[str, Any],
    latency_ms: int,
) -> dict[str, Any]:
    return {
        "schema_version": P45_LLM_RESEARCH_ARTICLE_SCHEMA_VERSION,
        "llm_research_run_id": research_run_id,
        "final_run_id": final_payload.get("final_run_id"),
        "article_run_id": final_payload.get("article_run_id"),
        "pack_id": final_payload.get("pack_id"),
        "p3_run_id": final_payload.get("p3_run_id"),
        "p2_radar_run_id": final_payload.get("p2_radar_run_id"),
        "collect_run_id": final_payload.get("collect_run_id"),
        "provider": provider,
        "model": model,
        "runtime_mode": runtime_mode,
        "status": status,
        "article": output.get("article", ""),
        "title": output.get("title", "P4.5 LLM 深度中文研报"),
        "core_view": output.get("core_view"),
        "evidence_ids_used": output.get("evidence_ids_used", []),
        "radar_modules_covered": output.get("radar_modules_covered", []),
        "metric_evidence_count_seen": context["summary"]["metric_evidence_count"],
        "created_at": datetime.now(UTC).isoformat(),
        "latency_ms": latency_ms,
        "error": None,
        "prompt_context_summary": context["summary"],
    }


def _failed_payload(
    research_run_id: str,
    runtime_mode: str,
    provider: str,
    model: str | None,
    final_payload: dict[str, Any],
    context: dict[str, Any],
    started: float,
    error: str,
) -> dict[str, Any]:
    return {
        "schema_version": P45_LLM_RESEARCH_ARTICLE_SCHEMA_VERSION,
        "llm_research_run_id": research_run_id,
        "final_run_id": final_payload.get("final_run_id"),
        "article_run_id": final_payload.get("article_run_id"),
        "pack_id": final_payload.get("pack_id"),
        "p3_run_id": final_payload.get("p3_run_id"),
        "p2_radar_run_id": final_payload.get("p2_radar_run_id"),
        "collect_run_id": final_payload.get("collect_run_id"),
        "provider": provider,
        "model": model,
        "runtime_mode": runtime_mode,
        "status": "failed",
        "article": "",
        "title": "P4.5 LLM 深度中文研报",
        "core_view": None,
        "evidence_ids_used": [],
        "radar_modules_covered": [],
        "metric_evidence_count_seen": context["summary"]["metric_evidence_count"],
        "created_at": datetime.now(UTC).isoformat(),
        "latency_ms": _latency_ms(started),
        "error": error,
        "prompt_context_summary": context["summary"],
    }


def _research_context(
    final_payload: dict[str, Any],
    article_payload: dict[str, Any],
    pack_payload: dict[str, Any],
) -> dict[str, Any]:
    modules = []
    metrics = []
    for analyst in pack_payload.get("analysts", []):
        for module in analyst.get("modules", []):
            modules.append(
                {
                    "analyst_id": analyst.get("analyst_id"),
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
                        "analyst_id": analyst.get("analyst_id"),
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
    analyst_articles = [
        {
            "analyst_id": item.get("analyst_id"),
            "title": item.get("title"),
            "direction_view": item.get("direction_view"),
            "score_summary": item.get("score_summary"),
            "article": item.get("article"),
        }
        for item in article_payload.get("analyst_articles", [])
    ]
    return {
        "lineage": {
            "collect_run_id": final_payload.get("collect_run_id"),
            "p2_radar_run_id": final_payload.get("p2_radar_run_id"),
            "p3_run_id": final_payload.get("p3_run_id"),
            "pack_id": final_payload.get("pack_id"),
            "article_run_id": final_payload.get("article_run_id"),
            "final_run_id": final_payload.get("final_run_id"),
        },
        "final_baseline": {
            "core_view": final_payload.get("core_view"),
            "direction_counts": final_payload.get("direction_counts"),
            "article": final_payload.get("article"),
        },
        "analyst_articles": analyst_articles,
        "radar_modules": modules,
        "metric_evidence": metrics,
        "summary": {
            "analyst_count": len(analyst_articles),
            "radar_module_count": len(modules),
            "metric_evidence_count": len(metrics),
            "positive": _count_bucket(metrics, "positive"),
            "negative": _count_bucket(metrics, "negative"),
            "zero": _count_bucket(metrics, "zero"),
            "unavailable": _count_bucket(metrics, "unavailable"),
        },
    }


def _system_prompt() -> str:
    return (
        "你是 onlyBTC 的 P4.5 Research Writer。你只基于输入 JSON 中的 "
        "P3 scored evidence、Radar module score 和四位分析员文章写中文研究报告。"
        "不要给交易指令，不要建议买卖或仓位。"
        "必须输出单个 JSON object，不要 markdown fence。"
    )


def _user_prompt(context: dict[str, Any]) -> str:
    return (
        "请读取下面的完整 P4.5 context，生成一篇专业 BTC 趋势研究长文。\n"
        "要求：\n"
        "1. 中文输出，写成可直接给人阅读的研究文章。\n"
        "2. 必须覆盖 14 个 Radar module 的主要结论。\n"
        "3. 必须引用 evidence_id、指标值、metric_score、module_score。\n"
        "4. 必须区分 positive / negative / zero / unavailable。\n"
        "5. unavailable 是数据边界，不可当成负面趋势。\n"
        "6. 要写趋势敏感点：哪些信号正在改善、恶化、分歧或等待确认。\n"
        "7. 输出 JSON schema：\n"
        "{\n"
        '  "title": "string",\n'
        '  "core_view": "bullish|bearish|mixed|neutral",\n'
        '  "article": "markdown text",\n'
        '  "evidence_ids_used": ["..."],\n'
        '  "radar_modules_covered": ["..."]\n'
        "}\n\n"
        "P4.5 context JSON:\n"
        + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    )


def _mock_article(context: dict[str, Any]) -> dict[str, Any]:
    module_lines = [
        (
            f"- {item['radar_module']}：module_score={item.get('module_score')}，"
            f"方向={item.get('module_direction')}。{item.get('module_explanation')}"
        )
        for item in context["radar_modules"]
    ]
    positive = [m for m in context["metric_evidence"] if m.get("score_bucket") == "positive"]
    negative = [m for m in context["metric_evidence"] if m.get("score_bucket") == "negative"]
    unavailable = [
        m for m in context["metric_evidence"] if m.get("score_bucket") == "unavailable"
    ]
    evidence_ids = [
        str(item["evidence_id"])
        for item in [*positive[:8], *negative[:8]]
        if item.get("evidence_id")
    ]
    article = "\n\n".join(
        [
            "# P4.5 LLM 深度中文研报（Mock）",
            (
                f"本轮模拟 LLM 读取 {context['summary']['metric_evidence_count']} 条 "
                f"scored evidence 和 {context['summary']['radar_module_count']} 个 "
                "Radar module。当前基线判断为 "
                f"{context['final_baseline'].get('core_view')}。"
            ),
            "## Radar 全局结构\n" + "\n".join(module_lines),
            (
                "## 多空证据\n"
                + _metric_brief_lines("正向", positive[:6])
                + "\n"
                + _metric_brief_lines("负向", negative[:6])
            ),
            "## 数据边界\n" + _metric_brief_lines("不可用", unavailable),
            (
                "## 观察路径\n"
                "24h 看短线动能和资金流是否同向；"
                "3d 看流动性与衍生品拥挤；"
                "7d 看宏观利率压力、链上采用度和估值是否共振。"
            ),
        ]
    )
    return {
        "title": "P4.5 LLM 深度中文研报（Mock）",
        "core_view": context["final_baseline"].get("core_view"),
        "article": article,
        "evidence_ids_used": evidence_ids,
        "radar_modules_covered": [item["radar_module"] for item in context["radar_modules"]],
    }


def _metric_brief_lines(label: str, metrics: list[dict[str, Any]]) -> str:
    if not metrics:
        return f"{label}：无。"
    return "\n".join(
        (
            f"{label}：{item.get('metric_id')} value={item.get('value')} "
            f"metric_score={item.get('metric_score')} evidence_id={item.get('evidence_id')}，"
            f"{item.get('p45_metric_brief') or item.get('score_reason')}"
        )
        for item in metrics
    )


def _repair_output(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    allowed_ids = {str(item.get("evidence_id")) for item in context["metric_evidence"]}
    allowed_ids.discard("None")
    module_ids = {str(item.get("radar_module")) for item in context["radar_modules"]}
    evidence_ids = [
        str(item)
        for item in payload.get("evidence_ids_used", [])
        if str(item) in allowed_ids
    ]
    modules = [
        str(item)
        for item in payload.get("radar_modules_covered", [])
        if str(item) in module_ids
    ]
    article = str(payload.get("article") or "")
    if not evidence_ids:
        evidence_ids = sorted(
            {
                evidence_id
                for evidence_id in allowed_ids
                if evidence_id and evidence_id in article
            }
        )
    return {
        "title": str(payload.get("title") or "P4.5 LLM 深度中文研报"),
        "core_view": str(payload.get("core_view") or context["final_baseline"].get("core_view")),
        "article": article,
        "evidence_ids_used": evidence_ids,
        "radar_modules_covered": modules,
    }


def _validate_output(payload: dict[str, Any], context: dict[str, Any]) -> str | None:
    if len(str(payload.get("article") or "")) < 800:
        return "article_too_short"
    if not payload.get("evidence_ids_used"):
        return "missing_evidence_ids_used"
    covered = set(payload.get("radar_modules_covered") or [])
    expected = {item["radar_module"] for item in context["radar_modules"]}
    missing_modules = sorted(expected - covered)
    if missing_modules:
        return "missing_radar_modules_covered: " + ", ".join(missing_modules)
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


def _load_payload(
    session,
    module_id: str,
    run_id: str | None = None,
) -> dict[str, Any] | None:
    query = select(schema.ModuleJsonOutput).where(
        schema.ModuleJsonOutput.module_id == module_id
    )
    if run_id:
        query = query.where(schema.ModuleJsonOutput.run_id == run_id)
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


def _generate_research_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"p45llm-{stamp}-{uuid4().hex[:6]}"
