from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from onlybtc.core.config import Settings, get_settings
from onlybtc.event_window.connectors.common import stable_hash

ALLOWED_TONES = {
    "hawkish",
    "dovish",
    "balanced",
    "ambiguous",
    "data_dependent",
    "not_policy_relevant",
}

PROHIBITED_DIRECTION_TERMS = (
    "btc bullish",
    "btc bearish",
    "bitcoin bullish",
    "bitcoin bearish",
    "buy btc",
    "sell btc",
    "long btc",
    "short btc",
    "看多btc",
    "看空btc",
    "买入btc",
    "卖出btc",
)

HAWKISH_TERMS = (
    "inflation remains elevated",
    "higher for longer",
    "restrictive",
    "not yet confident",
    "upside risks to inflation",
    "further tightening",
    "persistent inflation",
)

DOVISH_TERMS = (
    "cooling inflation",
    "disinflation",
    "labor market is softening",
    "rate cuts",
    "downside risks",
    "policy is restrictive enough",
    "progress on inflation",
)

DATA_DEPENDENT_TERMS = (
    "data dependent",
    "meeting by meeting",
    "incoming data",
    "totality of the data",
    "carefully assess",
)

POLICY_TOPICS = {
    "inflation": ("inflation", "prices", "pce", "cpi", "disinflation"),
    "labor": ("labor", "employment", "unemployment", "wages", "payroll"),
    "rates": ("rate", "federal funds", "policy stance", "restrictive", "cut"),
    "growth": ("growth", "gdp", "demand", "activity"),
    "financial_conditions": ("financial conditions", "credit", "liquidity", "market"),
}


def analyze_fed_texts(
    texts: list[dict[str, Any]],
    now: datetime | None = None,
    *,
    use_deepseek: bool = False,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Classify official Fed text without allowing LLMs to set BTC direction."""

    asof = _ensure_utc(now or datetime.now(UTC))
    settings = settings or get_settings()
    analyses: list[dict[str, Any]] = []
    for item in texts:
        deterministic = _deterministic_analysis(item, asof, settings)
        if use_deepseek and settings.deepseek_api_key:
            llm = _deepseek_analysis(item, deterministic, asof, settings)
            analyses.append(_merge_analysis(deterministic, llm))
        elif use_deepseek:
            deterministic["llm_status"] = "degraded"
            deterministic["llm_error"] = "deepseek_api_key_missing"
            analyses.append(deterministic)
        else:
            analyses.append(deterministic)
    return analyses


def boundary_audit(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    violations: list[str] = []
    for item in analyses:
        text = json.dumps(item, ensure_ascii=False).lower()
        if any(term in text for term in PROHIBITED_DIRECTION_TERMS):
            violations.append(f"{item.get('analysis_id')}: btc_direction_term_present")
        if str(item.get("tone") or "") not in ALLOWED_TONES:
            violations.append(f"{item.get('analysis_id')}: invalid_tone")
        if float(item.get("tone_confidence") or 0.0) < 0.70 and item.get(
            "tone_shift_vs_baseline"
        ):
            violations.append(f"{item.get('analysis_id')}: low_confidence_tone_shift")
        if str(item.get("policy_relevance") or "low") == "low" and item.get(
            "can_escalate_overlay"
        ):
            violations.append(f"{item.get('analysis_id')}: low_relevance_escalates_overlay")
    return {
        "schema_version": "p45.event_window.speech_analyzer.audit.v1",
        "analysis_count": len(analyses),
        "boundary_passed": not violations,
        "violations": violations,
        "deepseek_items": sum(
            1 for item in analyses if str(item.get("llm_provider") or "") == "deepseek"
        ),
        "degraded_items": sum(
            1 for item in analyses if str(item.get("llm_status") or "") == "degraded"
        ),
    }


def _deterministic_analysis(
    item: dict[str, Any], now: datetime, settings: Settings
) -> dict[str, Any]:
    text_id = str(item.get("text_id") or stable_hash(item)[:16])
    raw_text = _plain_text(str(item.get("raw_text") or item.get("title") or ""))
    speaker = str(item.get("speaker") or "")
    speaker_weight = _speaker_weight(speaker, str(item.get("title") or ""))
    tone, confidence = _classify_tone(raw_text)
    topics = _policy_topics(raw_text)
    relevance = _policy_relevance(tone, topics, speaker_weight)
    requires_review = confidence < 0.70 or tone in {"ambiguous", "data_dependent"}
    text_hash = str(item.get("text_hash") or stable_hash(raw_text))
    return {
        "analysis_id": f"analysis-{text_hash[:24]}",
        "text_id": text_id,
        "analysis_hash": stable_hash({"text_hash": text_hash, "version": "v1"}),
        "analyzed_at": now.isoformat(),
        "speaker": speaker,
        "speaker_weight": speaker_weight,
        "tone": tone,
        "tone_confidence": confidence,
        "policy_relevance": relevance,
        "tone_shift_vs_baseline": False,
        "requires_human_review": requires_review,
        "policy_topics": topics,
        "source_url": item.get("url") or "",
        "evidence_excerpt": raw_text[:260],
        "summary": _summary(tone, relevance, topics),
        "llm_provider": "deterministic",
        "llm_model": "",
        "llm_status": "not_requested",
        "llm_error": "",
        "deepseek_configured": bool(settings.deepseek_api_key),
        "can_escalate_overlay": (
            relevance in {"medium", "high"}
            and confidence >= 0.70
            and tone in {"hawkish", "dovish"}
        ),
        "direct_btc_score_impact": False,
        "btc_direction_boundary_pass": True,
    }


def _deepseek_analysis(
    item: dict[str, Any],
    fallback: dict[str, Any],
    now: datetime,
    settings: Settings,
) -> dict[str, Any]:
    base_url = settings.deepseek_base_url.rstrip("/")
    prompt = {
        "task": "Classify official Fed/policy text for Event Window overlay audit.",
        "strict_rules": [
            "Return JSON only.",
            "Do not output BTC bullish/bearish direction or trading recommendation.",
            "Do not modify actual, consensus, nowcast, radar score, or BTC score.",
            (
                "Allowed tone: hawkish, dovish, balanced, ambiguous, "
                "data_dependent, not_policy_relevant."
            ),
        ],
        "text": {
            "title": item.get("title"),
            "speaker": item.get("speaker"),
            "source_url": item.get("url"),
            "raw_text": str(item.get("raw_text") or "")[:6000],
        },
        "fallback": {
            "tone": fallback.get("tone"),
            "tone_confidence": fallback.get("tone_confidence"),
            "policy_relevance": fallback.get("policy_relevance"),
            "policy_topics": fallback.get("policy_topics"),
        },
    }
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a policy text classifier. Classify Fed text only. "
                    "Never give BTC direction, price target, or trade instruction. "
                    "Write summary and evidence_excerpt in Simplified Chinese."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt, ensure_ascii=False)
                + "\nReturn keys: tone, tone_confidence, policy_relevance, "
                "policy_topics, requires_human_review, summary, evidence_excerpt. "
                "The values of summary and evidence_excerpt must be Simplified Chinese.",
            },
        ],
        "temperature": 0.1,
        "stream": False,
    }
    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=min(settings.p45_research_timeout_seconds, 60),
        )
        response.raise_for_status()
        content = str(response.json()["choices"][0]["message"]["content"])
        parsed = _parse_json(content)
        parsed["llm_provider"] = "deepseek"
        parsed["llm_model"] = settings.deepseek_model
        parsed["llm_status"] = "success"
        parsed["llm_error"] = ""
        parsed["analyzed_at"] = now.isoformat()
        return parsed
    except Exception as exc:
        return {
            "llm_provider": "deepseek",
            "llm_model": settings.deepseek_model,
            "llm_status": "degraded",
            "llm_error": f"{type(exc).__name__}: {exc}",
            "analyzed_at": now.isoformat(),
        }


def _merge_analysis(fallback: dict[str, Any], llm: dict[str, Any]) -> dict[str, Any]:
    merged = dict(fallback)
    if llm.get("llm_status") == "success":
        tone = str(llm.get("tone") or fallback.get("tone"))
        merged["tone"] = tone if tone in ALLOWED_TONES else "ambiguous"
        merged["tone_confidence"] = _clamp_float(
            llm.get("tone_confidence"),
            fallback=float(fallback.get("tone_confidence") or 0.0),
        )
        relevance = str(llm.get("policy_relevance") or fallback.get("policy_relevance"))
        merged["policy_relevance"] = (
            relevance if relevance in {"low", "medium", "high"} else "low"
        )
        topics = llm.get("policy_topics")
        if isinstance(topics, list):
            merged["policy_topics"] = [str(item) for item in topics[:8]]
        merged["requires_human_review"] = bool(
            llm.get("requires_human_review")
            or merged["tone_confidence"] < 0.70
            or merged["tone"] in {"ambiguous", "data_dependent"}
        )
        merged["summary"] = str(llm.get("summary") or fallback.get("summary") or "")
        merged["evidence_excerpt"] = str(
            llm.get("evidence_excerpt") or fallback.get("evidence_excerpt") or ""
        )[:360]
    merged["llm_provider"] = llm.get("llm_provider", merged.get("llm_provider"))
    merged["llm_model"] = llm.get("llm_model", merged.get("llm_model"))
    merged["llm_status"] = llm.get("llm_status", merged.get("llm_status"))
    merged["llm_error"] = llm.get("llm_error", "")
    merged["can_escalate_overlay"] = (
        merged["policy_relevance"] in {"medium", "high"}
        and float(merged["tone_confidence"] or 0.0) >= 0.70
        and merged["tone"] in {"hawkish", "dovish"}
    )
    boundary = boundary_audit([merged])
    merged["btc_direction_boundary_pass"] = bool(boundary["boundary_passed"])
    if not boundary["boundary_passed"]:
        merged["requires_human_review"] = True
    return merged


def _classify_tone(text: str) -> tuple[str, float]:
    lower = text.lower()
    hawkish = sum(1 for term in HAWKISH_TERMS if term in lower)
    dovish = sum(1 for term in DOVISH_TERMS if term in lower)
    data_dependent = sum(1 for term in DATA_DEPENDENT_TERMS if term in lower)
    if hawkish > dovish and hawkish:
        return "hawkish", min(0.92, 0.68 + hawkish * 0.08)
    if dovish > hawkish and dovish:
        return "dovish", min(0.92, 0.68 + dovish * 0.08)
    if data_dependent:
        return "data_dependent", min(0.86, 0.66 + data_dependent * 0.06)
    if any(term in lower for term in ("federal reserve", "fomc", "fed", "policy")):
        return "balanced", 0.72
    return "not_policy_relevant", 0.95


def _policy_topics(text: str) -> list[str]:
    lower = text.lower()
    topics = [
        topic
        for topic, terms in POLICY_TOPICS.items()
        if any(term in lower for term in terms)
    ]
    return topics or ["general"]


def _policy_relevance(tone: str, topics: list[str], speaker_weight: float) -> str:
    if tone == "not_policy_relevant":
        return "low"
    score = speaker_weight + (0.25 if any(topic != "general" for topic in topics) else 0.0)
    if tone in {"hawkish", "dovish"}:
        score += 0.25
    if score >= 0.80:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _speaker_weight(speaker: str, title: str) -> float:
    text = f"{speaker} {title}".lower()
    if "powell" in text or "chair" in text:
        return 1.0
    if "vice chair" in text or "new york" in text or "ny fed" in text:
        return 0.85
    if "governor" in text or "board of governors" in text:
        return 0.75
    if "president" in text:
        return 0.55
    if speaker:
        return 0.40
    return 0.0


def _summary(tone: str, relevance: str, topics: list[str]) -> str:
    if tone == "not_policy_relevant":
        return "未检测到与货币政策立场直接相关的 Fed 语气变化。"
    return (
        f"政策文本分类为 {tone}；相关性为 {relevance}；"
        f"主题包括：{', '.join(topics)}。这是 Event Window 覆盖层输入，"
        "不是 BTC 方向信号。"
    )


def _parse_json(content: str) -> dict[str, Any]:
    text = content.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def _plain_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _clamp_float(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(0.0, min(1.0, parsed))


def _ensure_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
