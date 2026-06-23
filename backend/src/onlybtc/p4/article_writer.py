from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import TypeAdapter

from onlybtc.p4.agent_runtime import AgentRuntimeAdapter, RuntimeResult
from onlybtc.p4.prompts import build_analyst_article_prompt, build_final_article_prompt
from onlybtc.p4.schemas import AnalystId, AnalystReadableArticle, FinalObservationArticle

ArticleRuntimeMode = Literal["mock", "llm"]


def generate_readable_articles(
    analyst_narratives: list[dict[str, Any]],
    final_json: dict[str, Any],
    judge: dict[str, Any],
    review: dict[str, Any],
    state: dict[str, Any],
    article_runtime_mode: ArticleRuntimeMode = "mock",
    runtime: AgentRuntimeAdapter | None = None,
    full_evidence_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    runtime = runtime or AgentRuntimeAdapter()
    analyst_articles: list[dict[str, Any]] = []
    runtime_results: list[dict[str, Any]] = []
    errors: list[str] = []

    for narrative in analyst_narratives:
        context = _analyst_article_context(narrative, final_json, state)
        evidence_ids = _evidence_ids_from_narrative(narrative)
        narrative_evidence = _evidence_rows_from_narrative(narrative)
        prompt = build_analyst_article_prompt(
            analyst_id=_analyst_id(narrative),
            article_context=context,
            evidence_ids=evidence_ids,
        )
        result = _run_article_prompt(
            runtime=runtime,
            mode=article_runtime_mode,
            prompt=prompt,
            output_model=AnalystReadableArticle,
            fallback=_mock_analyst_article(narrative, final_json, state),
        )
        runtime_results.append(result.model_dump(mode="json"))
        if result.error:
            errors.append(f"{prompt.agent_id}/{_analyst_id(narrative)}: {result.error}")
        article = _ensure_article_evidence(
            result.structured_output or _mock_analyst_article(narrative, final_json, state),
            narrative_evidence,
            output_model=AnalystReadableArticle,
            appendix_heading="Evidence coverage appendix",
        )
        analyst_articles.append(
            _enhance_analyst_article(
                article=article,
                narrative=narrative,
                final_json=final_json,
                state=state,
                evidence_rows=narrative_evidence,
            )
        )

    all_article_evidence = [
        row
        for narrative in analyst_narratives
        for row in _evidence_rows_from_narrative(narrative)
    ]
    if full_evidence_rows is not None:
        all_article_evidence = _unique_evidence_rows(
            all_article_evidence + [row for row in full_evidence_rows if row.get("evidence_id")]
        )
    final_context = {
        "final_controller": _article_safe_final_controller(final_json),
        "judge_synthesis": judge,
        "adversarial_review": review,
        "state_machine": state,
        "publish_gate_summary": _publish_gate_summary(final_json, state),
        "quality_readiness_summary": _quality_readiness_summary(final_json),
        "analyst_articles": analyst_articles,
        "trend_frame": _build_final_trend_frame(
            analyst_articles=analyst_articles,
            evidence_rows=all_article_evidence,
            final_json=final_json,
            judge=judge,
        ),
        "full_evidence_index": _compact_evidence_rows(all_article_evidence),
    }
    final_evidence_ids = _unique(
        list(final_json.get("evidence_ids") or [])
        + _article_ids(analyst_articles)
        + _history_reference_evidence_ids(analyst_articles)
        + [str(row["evidence_id"]) for row in all_article_evidence if row.get("evidence_id")]
    )
    final_prompt = build_final_article_prompt(final_context, final_evidence_ids)
    final_result = _run_article_prompt(
        runtime=runtime,
        mode=article_runtime_mode,
        prompt=final_prompt,
        output_model=FinalObservationArticle,
        fallback=_mock_final_article(final_json, judge, review, state, analyst_articles),
    )
    runtime_results.append(final_result.model_dump(mode="json"))
    if final_result.error:
        errors.append(f"{final_prompt.agent_id}/final: {final_result.error}")
    final_article = _ensure_article_evidence(
        final_result.structured_output
        or _mock_final_article(final_json, judge, review, state, analyst_articles),
        all_article_evidence,
        output_model=FinalObservationArticle,
        appendix_heading="Full evidence coverage appendix",
    )
    final_article = _enhance_final_article(
        article=final_article,
        final_json=final_json,
        judge=judge,
        review=review,
        state=state,
        analyst_articles=analyst_articles,
        evidence_rows=all_article_evidence,
    )

    return {
        "status": "completed_with_errors" if errors else "completed",
        "article_runtime_mode": article_runtime_mode,
        "analyst_articles": analyst_articles,
        "final_article": final_article,
        "runtime_results": runtime_results,
        "errors": errors,
    }


def _run_article_prompt(
    runtime: AgentRuntimeAdapter,
    mode: ArticleRuntimeMode,
    prompt: Any,
    output_model: type[AnalystReadableArticle] | type[FinalObservationArticle],
    fallback: dict[str, Any],
) -> RuntimeResult:
    if mode == "llm":
        result = runtime.run_openai_compatible_chat(prompt, output_model)
        if result.succeeded:
            return result
        return result
    return runtime.run_mock(prompt, output_model, structured_output=fallback)


def _analyst_article_context(
    narrative: dict[str, Any],
    final_json: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    trend_frame = narrative.get("trend_frame") or _build_trend_frame(
        rows=_evidence_rows_from_narrative(narrative),
        vote=str(narrative.get("vote") or "unknown"),
        confidence=narrative.get("confidence"),
        history_summary=str(narrative.get("history_summary") or ""),
        final_json=final_json,
    )
    return {
        "analyst_id": narrative.get("raw_analyst_id"),
        "display_name": narrative.get("analyst_id"),
        "modules": narrative.get("modules"),
        "vote": narrative.get("vote"),
        "confidence": narrative.get("confidence"),
        "evidence_count": narrative.get("evidence_count"),
        "trend_frame": trend_frame,
        "sensitive_evidence": _compact_evidence_rows(
            _sensitive_evidence_rows(_evidence_rows_from_narrative(narrative), limit=10)
        ),
        "top_evidence": narrative.get("top_evidence") or [],
        "all_evidence": _compact_evidence_rows(narrative.get("all_evidence") or []),
        "evidence_by_module": narrative.get("evidence_by_module") or [],
        "coverage_target_evidence_ids": narrative.get("coverage_target_evidence_ids") or [],
        "history_summary": narrative.get("history_summary"),
        "deterministic_conclusion": narrative.get("conclusion"),
        "final_state": {
            "trend_state": final_json.get("trend_state"),
            "risk_state": final_json.get("risk_state"),
            "blocked_by": final_json.get("blocked_by") or [],
            "publish_allowed": final_json.get("publish_allowed"),
            "publish_scope": final_json.get("publish_scope"),
            "publish_block_reason": final_json.get("publish_block_reason"),
        },
        "quality_readiness_summary": _quality_readiness_summary(final_json),
        "state_machine": {
            "critical_publish_allowed": state.get("critical_publish_allowed"),
            "state_transition_allowed": state.get("state_transition_allowed"),
        },
    }


def _build_trend_frame(
    rows: list[dict[str, Any]],
    vote: str,
    confidence: Any,
    history_summary: str,
    final_json: dict[str, Any],
) -> dict[str, Any]:
    available = [row for row in rows if row.get("available") is not False]
    working_rows = available or rows
    directional = [row for row in working_rows if str(row.get("direction") or "neutral")]
    bullish = [row for row in directional if str(row.get("direction")) == "bullish"]
    bearish = [row for row in directional if str(row.get("direction")) in {"bearish", "risk_off"}]
    mixed = [row for row in directional if str(row.get("direction")) in {"mixed", "neutral"}]
    score = sum(_direction_weight(row) for row in directional)
    if score > 0.12:
        impulse = "bullish impulse"
    elif score < -0.12:
        impulse = "bearish impulse"
    else:
        impulse = "mixed or fragile impulse"
    sensitive = _sensitive_evidence_rows(working_rows, limit=8)
    strongest = _sorted_by_strength(working_rows, limit=8)
    conflicts = _conflict_pairs(bullish, bearish)
    blocked_by = ", ".join(str(item) for item in final_json.get("blocked_by") or []) or "none"
    return {
        "trend_impulse": (
            f"{impulse}; analyst_vote={vote}; confidence={confidence}; "
            f"weighted_direction_score={score:.4f}; bullish_count={len(bullish)}; "
            f"bearish_count={len(bearish)}; mixed_or_neutral_count={len(mixed)}"
        ),
        "marginal_change": history_summary or "No analyst history was available in this run.",
        "sensitive_signals": [_evidence_readable(row) for row in sensitive],
        "strongest_signals": [_evidence_readable(row) for row in strongest],
        "conflict_weighting": conflicts,
        "scenario_map": [
            "偏多确认：敏感偏多证据继续扩散，同时偏空冲突证据减弱。",
            "偏空确认：资金费率、杠杆、资金流或宏观压力证据同步转弱。",
            "中性观察：多空证据数量和质量继续抵消，事件约束仍然存在。",
        ],
        "invalidation_conditions": [
            "current directional score flips sign with higher-quality evidence",
            "top sensitive evidence changes direction or becomes unavailable",
            f"state constraints change materially; current blocked_by={blocked_by}",
        ],
        "watch_horizon": [
            "24h: short-cycle kline/order-flow, funding, OI, taker ratio, ETF flow",
            "3d: stablecoin supply, exchange balance, macro risk and event-window updates",
            "7d: onchain valuation, breadth, adoption and post-event confirmation",
        ],
        "audit_constraints_summary": (
            "Publish/runtime gates affect confidence and presentation scope; they should "
            "not replace the trend analysis itself."
        ),
    }


def _enhance_analyst_article(
    article: dict[str, Any],
    narrative: dict[str, Any],
    final_json: dict[str, Any],
    state: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    trend_frame = _build_trend_frame(
        rows=evidence_rows,
        vote=str(narrative.get("vote") or "unknown"),
        confidence=narrative.get("confidence"),
        history_summary=str(narrative.get("history_summary") or ""),
        final_json=final_json,
    )
    title = str(article.get("title") or narrative.get("analyst_id") or "分析师研究简报")
    if title.startswith("1.") or title.startswith("一、"):
        title = f"{narrative.get('analyst_id') or '分析师'}：本轮模块研究简报"
    article["title"] = title
    article["summary"] = _first_non_repair_text(
        article.get("summary"),
        article.get("core_view"),
        _module_thesis(narrative, evidence_rows, trend_frame),
    )
    trend_insight = str(article.get("trend_insight") or "")
    article["trend_insight"] = (
        _human_trend_summary(trend_frame, final_json)
        if not trend_insight or "weighted_direction_score" in trend_insight
        else trend_insight
    )
    article["marginal_change"] = article.get("marginal_change") or str(
        trend_frame["marginal_change"]
    )
    article["sensitive_signals"] = _nonempty_list(
        article.get("sensitive_signals"),
        list(trend_frame["sensitive_signals"])[:6],
    )
    article["early_warning_signals"] = _nonempty_list(
        article.get("early_warning_signals"),
        list(trend_frame["strongest_signals"])[:5],
    )
    article["conflict_weighting"] = article.get("conflict_weighting") or "; ".join(
        trend_frame["conflict_weighting"]
    )
    article["scenario_map"] = _nonempty_list(
        article.get("scenario_map"),
        list(trend_frame["scenario_map"]),
    )
    article["invalidation_conditions"] = _nonempty_list(
        article.get("invalidation_conditions"),
        list(trend_frame["invalidation_conditions"]),
    )
    article["watch_horizon"] = _nonempty_list(
        article.get("watch_horizon"),
        list(trend_frame["watch_horizon"]),
    )
    article["confidence_explanation"] = article.get("confidence_explanation") or (
        f"本模块 confidence={narrative.get('confidence')}，证据数="
        f"{len(evidence_rows)}；置信度主要受证据冲突、质量和历史变化影响。"
    )
    article["audit_constraints_summary"] = article.get(
        "audit_constraints_summary"
    ) or str(trend_frame["audit_constraints_summary"])
    article["sections"] = _dedupe_sections(
        _analyst_research_sections(narrative, evidence_rows, trend_frame)
        + list(article.get("sections") or [])
    )
    article = _dedupe_article_text_fields(article, final=False)
    return TypeAdapter(AnalystReadableArticle).validate_python(article).model_dump(mode="json")


def _enhance_final_article(
    article: dict[str, Any],
    final_json: dict[str, Any],
    judge: dict[str, Any],
    review: dict[str, Any],
    state: dict[str, Any],
    analyst_articles: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    trend_frame = _build_final_trend_frame(
        analyst_articles=analyst_articles,
        evidence_rows=evidence_rows,
        final_json=final_json,
        judge=judge,
    )
    thesis = _final_market_thesis(final_json, judge, analyst_articles, trend_frame)
    article["title"] = _research_title(article.get("title"), final_json)
    article["summary"] = thesis
    article["trend_insight"] = _trend_sentence(trend_frame, final_json)
    article["marginal_change"] = _history_delta_sentence(analyst_articles, trend_frame)
    article["sensitive_signals"] = list(trend_frame["sensitive_signals"])[:8]
    article["early_warning_signals"] = list(trend_frame["strongest_signals"])[:6]
    article["conflict_weighting"] = _conflict_sentence(trend_frame)
    article["scenario_map"] = _scenario_map(final_json, trend_frame)
    article["invalidation_conditions"] = _invalidation_conditions(trend_frame)
    article["watch_horizon"] = list(trend_frame["watch_horizon"])
    article["confidence_explanation"] = (
        f"最终 confidence={final_json.get('confidence')}，"
        f"confidence_discount={final_json.get('confidence_discount')}；"
        f"主裁判共识={judge.get('consensus_level')}，分歧={judge.get('disagreement_level')}。"
    )
    article["audit_constraints_summary"] = (
        f"publish_scope={final_json.get('publish_scope')}，blocked_by="
        f"{final_json.get('blocked_by') or []}，adversarial_passed={review.get('passed')}。"
    )
    article["executive_summary"] = thesis
    article["market_state"] = _market_state_sentence(final_json, judge, trend_frame)
    article["driver_analysis"] = _driver_sentence(evidence_rows)
    article["conflict_analysis"] = _conflict_sentence(trend_frame)
    article["history_delta"] = _history_delta_sentence(analyst_articles, trend_frame)
    article["event_watch"] = _event_watch_sentence(evidence_rows)
    article["quality_and_runtime"] = _quality_readiness_text(final_json)
    article["final_observation"] = _final_observation_sentence(final_json, trend_frame)
    article["sections"] = _dedupe_sections(
        _final_research_sections(
            final_json=final_json,
            judge=judge,
            state=state,
            analyst_articles=analyst_articles,
            evidence_rows=evidence_rows,
            trend_frame=trend_frame,
        )
        + list(article.get("sections") or [])
    )
    article["analyst_article_titles"] = [
        str(item.get("title")) for item in analyst_articles if item.get("title")
    ]
    article = _dedupe_article_text_fields(article, final=True)
    return TypeAdapter(FinalObservationArticle).validate_python(article).model_dump(
        mode="json"
    )


def _analyst_research_sections(
    narrative: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    trend_frame: dict[str, Any],
) -> list[dict[str, Any]]:
    ids = _row_ids(evidence_rows)
    strongest = _sorted_by_strength(evidence_rows, 6)
    sensitive = _sensitive_evidence_rows(evidence_rows, 6)
    return [
        {
            "heading": "趋势判断与边际变化",
            "body": _module_thesis(narrative, evidence_rows, trend_frame),
            "evidence_ids": ids[:8],
        },
        {
            "heading": "关键数据与机制解释",
            "body": "；".join(_evidence_readable(row) for row in strongest[:5]),
            "evidence_ids": _row_ids(strongest[:5]),
        },
        {
            "heading": "敏感信号与反证条件",
            "body": (
                "敏感信号：" + "；".join(_evidence_readable(row) for row in sensitive[:4])
                + "。反证条件：" + "；".join(trend_frame["invalidation_conditions"])
            ),
            "evidence_ids": _row_ids(sensitive[:4]) or ids[:4],
        },
        {
            "heading": "观察路径",
            "body": "；".join(trend_frame["watch_horizon"]),
            "evidence_ids": ids[:4],
        },
    ]


def _final_research_sections(
    final_json: dict[str, Any],
    judge: dict[str, Any],
    state: dict[str, Any],
    analyst_articles: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    trend_frame: dict[str, Any],
) -> list[dict[str, Any]]:
    by_module = _rows_by_module(evidence_rows)
    macro_rows = _module_rows(
        by_module,
        ("macro_radar", "treasury_credit", "asia_risk", "event_policy"),
    )
    liquidity_rows = _module_rows(by_module, ("dollar_liquidity", "fund_flow", "btc_adoption"))
    leverage_rows = _module_rows(
        by_module, ("derivatives_crowding", "trade_structure_flow", "options_volatility")
    )
    onchain_rows = _module_rows(
        by_module, ("onchain_valuation", "crypto_breadth", "btc_total_state", "kline_orderflow")
    )
    fallback_ids = _row_ids(evidence_rows) or ["mock-evidence"]
    return [
        {
            "heading": "一、核心结论：趋势方向与信号强度",
            "body": _final_market_thesis(final_json, judge, analyst_articles, trend_frame),
            "evidence_ids": _safe_ids(_sorted_by_strength(evidence_rows, 8), fallback_ids),
        },
        {
            "heading": "二、宏观与事件：风险偏好支撑但事件窗口仍需跟踪",
            "body": _module_body(macro_rows),
            "evidence_ids": _safe_ids(_sorted_by_strength(macro_rows, 8), fallback_ids),
        },
        {
            "heading": "三、流动性与资金流：资金条件和真实流入之间的分歧",
            "body": _module_body(liquidity_rows),
            "evidence_ids": _safe_ids(_sorted_by_strength(liquidity_rows, 8), fallback_ids),
        },
        {
            "heading": "四、杠杆与微观结构：短周期仓位和订单流的敏感变化",
            "body": _module_body(leverage_rows),
            "evidence_ids": _safe_ids(_sorted_by_strength(leverage_rows, 8), fallback_ids),
        },
        {
            "heading": "五、链上与市场结构：价格结构、估值和广度共同验证",
            "body": _module_body(onchain_rows),
            "evidence_ids": _safe_ids(_sorted_by_strength(onchain_rows, 8), fallback_ids),
        },
        {
            "heading": "六、冲突权重：哪一侧证据更容易先被验证",
            "body": _conflict_sentence(trend_frame),
            "evidence_ids": _safe_ids(_sorted_by_strength(evidence_rows, 8), fallback_ids),
        },
        {
            "heading": "七、情景树与反证条件",
            "body": "；".join(_scenario_map(final_json, trend_frame))
            + "。反证条件："
            + "；".join(_invalidation_conditions(trend_frame)),
            "evidence_ids": _safe_ids(_sensitive_evidence_rows(evidence_rows, 8), fallback_ids),
        },
        {
            "heading": "八、未来观察路径与数据边界",
            "body": (
                "观察周期：" + "；".join(trend_frame["watch_horizon"]) + "。"
                + _quality_readiness_text(final_json)
            ),
            "evidence_ids": _safe_ids(_sensitive_evidence_rows(evidence_rows, 8), fallback_ids),
        },
    ]


def _build_final_trend_frame(
    analyst_articles: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    final_json: dict[str, Any],
    judge: dict[str, Any],
) -> dict[str, Any]:
    base = _build_trend_frame(
        rows=evidence_rows,
        vote=str(final_json.get("base_signal") or final_json.get("trend_state") or "unknown"),
        confidence=final_json.get("confidence"),
        history_summary="; ".join(
            str(article.get("changed_from_history") or article.get("marginal_change") or "")
            for article in analyst_articles
            if article.get("changed_from_history") or article.get("marginal_change")
        )[:1200],
        final_json=final_json,
    )
    base["judge_context"] = {
        "consensus_level": judge.get("consensus_level"),
        "disagreement_level": judge.get("disagreement_level"),
        "dominant_regime": judge.get("dominant_regime"),
    }
    base["analyst_trend_views"] = [
        {
            "analyst_id": article.get("analyst_id"),
            "title": article.get("title"),
            "trend_insight": article.get("trend_insight") or article.get("core_view"),
            "confidence": article.get("confidence_explanation")
            or article.get("confidence_rationale"),
        }
        for article in analyst_articles
    ]
    return base


def _direction_weight(row: dict[str, Any]) -> float:
    direction = str(row.get("direction") or "neutral")
    polarity = {"bullish": 1.0, "bearish": -1.0, "risk_off": -1.0}.get(direction, 0.0)
    try:
        strength = abs(float(row.get("strength") or 0.0))
    except (TypeError, ValueError):
        strength = 0.0
    try:
        quality = float(row.get("quality_score") or 0.5)
    except (TypeError, ValueError):
        quality = 0.5
    return polarity * strength * max(0.25, quality)


def _sensitive_evidence_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    keywords = (
        "1h",
        "funding",
        "open_interest",
        "oi",
        "taker",
        "etf",
        "stablecoin",
        "exchange_balance",
        "vix",
        "dxy",
        "event",
        "days_until",
        "macro_surprise",
        "options",
        "basis",
    )

    def score(row: dict[str, Any]) -> tuple[int, float]:
        text = " ".join(
            str(row.get(key) or "")
            for key in ("metric_id", "source_id", "module_id", "claim", "role")
        ).lower()
        keyword_score = sum(1 for keyword in keywords if keyword in text)
        try:
            strength = abs(float(row.get("strength") or 0.0))
        except (TypeError, ValueError):
            strength = 0.0
        return keyword_score, strength

    return sorted(rows, key=score, reverse=True)[:limit]


def _sorted_by_strength(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    def score(row: dict[str, Any]) -> tuple[float, float]:
        try:
            strength = abs(float(row.get("strength") or 0.0))
        except (TypeError, ValueError):
            strength = 0.0
        try:
            quality = float(row.get("quality_score") or 0.0)
        except (TypeError, ValueError):
            quality = 0.0
        return strength, quality

    return sorted(rows, key=score, reverse=True)[:limit]


def _conflict_pairs(
    bullish: list[dict[str, Any]], bearish: list[dict[str, Any]]
) -> list[str]:
    pairs: list[str] = []
    for bull, bear in zip(
        _sorted_by_strength(bullish, 4),
        _sorted_by_strength(bearish, 4),
        strict=False,
    ):
        pairs.append(
            f"偏多证据 {_evidence_readable(bull)}，"
            f"对照偏空证据 {_evidence_readable(bear)}"
        )
    if not pairs:
        pairs.append("本组证据没有形成强烈的双向冲突，主要矛盾来自信号强度不足或方向分散。")
    return pairs


def _evidence_digest(row: dict[str, Any]) -> str:
    pieces = [
        str(row.get("evidence_id") or "unknown-evidence"),
        f"metric={row.get('metric_id')}",
        f"source={row.get('source_id')}",
        f"value={row.get('value')}",
        f"direction={row.get('direction')}",
        f"strength={row.get('strength')}",
        f"quality={row.get('quality_score')}",
    ]
    claim = row.get("claim") or row.get("event_headline")
    if claim:
        pieces.append(f"note={claim}")
    return " ".join(pieces)


def _direction_cn(value: Any) -> str:
    return {
        "bullish": "偏多",
        "bearish": "偏空",
        "risk_off": "风险偏空",
        "mixed": "混合",
        "neutral": "中性",
    }.get(str(value or "neutral"), str(value or "中性"))


def _value_cn(value: Any) -> str:
    if value is None:
        return "暂无数值"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _evidence_readable(row: dict[str, Any]) -> str:
    evidence_id = row.get("evidence_id") or "unknown-evidence"
    metric = row.get("metric_id") or row.get("event_headline") or "unknown_metric"
    source = row.get("source_id") or "unknown_source"
    direction = _direction_cn(row.get("direction"))
    value = _value_cn(row.get("value"))
    strength = _value_cn(row.get("strength"))
    quality = _value_cn(row.get("quality_score"))
    claim = str(row.get("claim") or row.get("event_headline") or "").strip()
    note = f"，注释：{claim}" if claim else ""
    return (
        f"{metric} 当前值 {value}，来源 {source}，方向 {direction}，"
        f"强度 {strength}，质量 {quality}（{evidence_id}）{note}"
    )


def _human_trend_summary(trend_frame: dict[str, Any], final_json: dict[str, Any]) -> str:
    impulse = str(trend_frame.get("trend_impulse") or "")
    score_match = re.search(r"weighted_direction_score=([-0-9.]+)", impulse)
    bullish_match = re.search(r"bullish_count=(\d+)", impulse)
    bearish_match = re.search(r"bearish_count=(\d+)", impulse)
    mixed_match = re.search(r"mixed_or_neutral_count=(\d+)", impulse)
    confidence_match = re.search(r"confidence=([^;]+)", impulse)
    score = score_match.group(1) if score_match else "未知"
    bullish = bullish_match.group(1) if bullish_match else "未知"
    bearish = bearish_match.group(1) if bearish_match else "未知"
    mixed = mixed_match.group(1) if mixed_match else "未知"
    confidence = confidence_match.group(1) if confidence_match else final_json.get("confidence")
    if "bullish impulse" in impulse:
        label = "偏多冲量"
        meaning = "多头证据的质量加权贡献略占上风"
    elif "bearish impulse" in impulse:
        label = "偏空冲量"
        meaning = "空头证据的质量加权贡献略占上风"
    else:
        label = "混合且脆弱的冲量"
        meaning = "多空证据互相抵消，趋势需要等待新的同向验证"
    publish_part = (
        f"，发布范围为 {final_json.get('publish_scope')}"
        if final_json.get("publish_scope") is not None
        else ""
    )
    return (
        f"本轮信号呈现{label}，质量加权方向分为 {score}，"
        f"偏多/偏空/中性证据数量分别为 {bullish}/{bearish}/{mixed}。"
        f"这意味着{meaning}；当前综合信心约为 {confidence}，"
        f"需要观察后续高质量信号是否继续同向扩散{publish_part}。"
    )


def _row_ids(rows: list[dict[str, Any]]) -> list[str]:
    return _unique([str(row["evidence_id"]) for row in rows if row.get("evidence_id")])


def _safe_ids(rows: list[dict[str, Any]], fallback_ids: list[str]) -> list[str]:
    return _row_ids(rows) or fallback_ids[:1]


def _rows_by_module(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("module_id") or "unknown"), []).append(row)
    return grouped


def _module_rows(
    grouped: dict[str, list[dict[str, Any]]],
    module_ids: tuple[str, ...],
) -> list[dict[str, Any]]:
    return [row for module_id in module_ids for row in grouped.get(module_id, [])]


def _module_body(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "本模块本轮没有可用证据，需等待下一轮数据补齐。"
    bullish = sum(1 for row in rows if row.get("direction") == "bullish")
    bearish = sum(1 for row in rows if row.get("direction") == "bearish")
    mixed = len(rows) - bullish - bearish
    strongest = _sorted_by_strength(rows, 6)
    return (
        f"本组证据共 {len(rows)} 项：看涨 {bullish} 项、看空 {bearish} 项、"
        f"混合/中性 {mixed} 项。最关键数据是："
        + "；".join(_evidence_readable(row) for row in strongest)
        + "。这些数据共同决定该模块对当前趋势的边际贡献，重点看同向扩散还是相互抵消。"
    )


def _module_thesis(
    narrative: dict[str, Any],
    rows: list[dict[str, Any]],
    trend_frame: dict[str, Any],
) -> str:
    return (
        f"{narrative.get('analyst_id')} 本轮 vote={narrative.get('vote')}，"
        f"confidence={narrative.get('confidence')}。"
        f"{_human_trend_summary(trend_frame, final_json={})}。"
        f"该判断来自 {len(rows)} 条证据，重点不是单点数值，而是方向、强度、"
        "质量和历史上下文共同形成的边际变化。"
    )


def _research_title(value: Any, final_json: dict[str, Any]) -> str:
    title = str(value or "").strip()
    if not title or title.startswith(("1.", "一、", "二、", "三、")):
        return (
            "BTC 多维雷达研究报告："
            f"{final_json.get('trend_state')} / {final_json.get('risk_state')}"
        )
    return title


def _final_market_thesis(
    final_json: dict[str, Any],
    judge: dict[str, Any],
    analyst_articles: list[dict[str, Any]],
    trend_frame: dict[str, Any],
) -> str:
    views = [
        f"{article.get('analyst_id')}={article.get('trend_insight') or article.get('summary')}"
        for article in analyst_articles
    ][:4]
    return (
        f"本轮 BTC 综合状态为 {final_json.get('trend_state')}，"
        f"风险状态为 {final_json.get('risk_state')}；主裁判给出的主导体制为 "
        f"{judge.get('dominant_regime')}，共识={judge.get('consensus_level')}，"
        f"分歧={judge.get('disagreement_level')}。"
        f"{_human_trend_summary(trend_frame, final_json)}"
        "四个分析师并非给出单一同向结论，而是在宏观、流动性、微观结构和链上结构"
        "之间形成交叉验证："
        + "；".join(views)
    )


def _trend_sentence(trend_frame: dict[str, Any], final_json: dict[str, Any]) -> str:
    return _human_trend_summary(trend_frame, final_json)


def _market_state_sentence(
    final_json: dict[str, Any],
    judge: dict[str, Any],
    trend_frame: dict[str, Any],
) -> str:
    return (
        f"trend_state={final_json.get('trend_state')}，risk_state={final_json.get('risk_state')}，"
        f"dominant_regime={judge.get('dominant_regime')}。"
        f"当前趋势解释为：{_human_trend_summary(trend_frame, final_json)}"
    )


def _driver_sentence(rows: list[dict[str, Any]]) -> str:
    strongest = _sorted_by_strength(rows, 10)
    return "关键驱动按强度排序为：" + "；".join(_evidence_readable(row) for row in strongest)


def _conflict_sentence(trend_frame: dict[str, Any]) -> str:
    return "主要冲突权重：" + "；".join(trend_frame["conflict_weighting"])


def _history_delta_sentence(
    analyst_articles: list[dict[str, Any]],
    trend_frame: dict[str, Any],
) -> str:
    history = [
        str(article.get("changed_from_history") or article.get("marginal_change") or "")
        for article in analyst_articles
        if article.get("changed_from_history") or article.get("marginal_change")
    ]
    return "；".join(history)[:1200] or str(trend_frame.get("marginal_change") or "")


def _event_watch_sentence(rows: list[dict[str, Any]]) -> str:
    event_rows = [
        row
        for row in rows
        if "days_until" in str(row.get("metric_id") or "")
        or "event" in str(row.get("module_id") or "")
    ]
    if not event_rows:
        return "本轮没有突出的事件窗口变化。"
    return "事件窗口观察：" + "；".join(_evidence_readable(row) for row in event_rows[:8])


def _final_observation_sentence(
    final_json: dict[str, Any],
    trend_frame: dict[str, Any],
) -> str:
    return (
        "当前结论应理解为趋势观察而非交易指令。"
        f"{_human_trend_summary(trend_frame, final_json)}若敏感信号继续同向扩张，"
        "趋势可信度会上升；若冲突证据反向验证，则需要下调结论强度。"
        f"当前 publish_scope={final_json.get('publish_scope')}。"
    )


def _scenario_map(
    final_json: dict[str, Any],
    trend_frame: dict[str, Any],
) -> list[str]:
    return [
        "看涨延续：质量加权方向分继续改善，资金流和微观结构同步转强。",
        "看跌反转：强度最高的敏感指标转向看空，且链上/流动性同时恶化。",
        f"中性震荡：confidence 维持在 {final_json.get('confidence')} 附近，"
        "多空证据继续抵消。",
    ]


def _invalidation_conditions(trend_frame: dict[str, Any]) -> list[str]:
    return list(trend_frame.get("invalidation_conditions") or [])[:5]


def _first_non_repair_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text and "Runtime schema repair applied" not in text:
            return text
    return "本轮文章由结构化证据生成，需结合证据附录阅读。"


def _nonempty_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list) and [item for item in value if item]:
        return [str(item) for item in value if item]
    return fallback


def _dedupe_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for section in sections:
        heading = str(section.get("heading") or "").strip()
        body = str(section.get("body") or "").strip()
        if "Runtime schema repair applied" in body:
            continue
        key = (heading, body[:240])
        if heading and body and key not in seen:
            seen.add(key)
            result.append(section)
    return result


def _dedupe_article_text_fields(article: dict[str, Any], final: bool) -> dict[str, Any]:
    keys = (
        [
            "summary",
            "executive_summary",
            "market_state",
            "driver_analysis",
            "conflict_analysis",
            "history_delta",
            "event_watch",
            "quality_and_runtime",
            "final_observation",
        ]
        if final
        else ["summary", "headline", "core_view", "confidence_rationale"]
    )
    seen: set[str] = set()
    for key in keys:
        text = str(article.get(key) or "").strip()
        normalized = re.sub(r"\s+", "", text)[:260]
        if not text:
            continue
        if "Runtime schema repair applied" in text or normalized in seen:
            article[key] = None if key != "summary" else article.get("trend_insight") or text
        else:
            seen.add(normalized)
    return article


def _mock_analyst_article(
    narrative: dict[str, Any],
    final_json: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    evidence_ids = _evidence_ids_from_narrative(narrative)
    primary_id = evidence_ids[0]
    evidence_rows = _evidence_rows_from_narrative(narrative)
    trend_frame = _build_trend_frame(
        rows=evidence_rows,
        vote=str(narrative.get("vote") or "unknown"),
        confidence=narrative.get("confidence"),
        history_summary=str(narrative.get("history_summary") or ""),
        final_json=final_json,
    )
    title = f"{narrative.get('analyst_id')} 本轮审计结论"
    summary = (
        f"该分析师本轮 vote={narrative.get('vote')}，confidence={narrative.get('confidence')}。"
        f"结论以 {primary_id} 等证据为基础，并受 trend_state={final_json.get('trend_state')}、"
        f"risk_state={final_json.get('risk_state')} 约束。"
    )
    citations = [_citation_from_evidence(row) for row in evidence_rows] or [
        {"evidence_id": primary_id, "note": "本轮没有展开的 evidence data。"}
    ]
    return TypeAdapter(AnalystReadableArticle).validate_python(
        {
            "analyst_id": _analyst_id(narrative),
            "title": title,
            "summary": summary,
            "trend_insight": _human_trend_summary(trend_frame, final_json),
            "marginal_change": str(trend_frame["marginal_change"]),
            "sensitive_signals": list(trend_frame["sensitive_signals"]),
            "early_warning_signals": list(trend_frame["strongest_signals"])[:5],
            "conflict_weighting": "; ".join(trend_frame["conflict_weighting"]),
            "scenario_map": list(trend_frame["scenario_map"]),
            "invalidation_conditions": list(trend_frame["invalidation_conditions"]),
            "watch_horizon": list(trend_frame["watch_horizon"]),
            "confidence_explanation": str(trend_frame["audit_constraints_summary"]),
            "audit_constraints_summary": str(trend_frame["audit_constraints_summary"]),
            "headline": title,
            "core_view": str(narrative.get("conclusion") or summary),
            "key_drivers": [
                str(row.get("claim") or row.get("metric_id") or row.get("evidence_id"))
                for row in evidence_rows[:5]
            ],
            "counter_evidence": [],
            "changed_from_history": str(
                narrative.get("history_summary") or "本轮没有可用历史记录。"
            ),
            "watch_items": [
                str(row.get("metric_id") or row.get("evidence_id"))
                for row in evidence_rows[:5]
            ],
            "confidence_rationale": (
                f"confidence={narrative.get('confidence')}，证据数量="
                f"{narrative.get('evidence_count')}，并受数据质量与状态机约束。"
            ),
            "sections": [
                {
                    "heading": "证据结论",
                    "body": narrative.get("conclusion") or summary,
                    "evidence_ids": evidence_ids,
                },
                {
                    "heading": "历史连续性",
                    "body": str(narrative.get("history_summary") or "本轮没有可用历史记录。"),
                    "evidence_ids": evidence_ids,
                },
            ],
            "evidence_citations": citations,
            "data_source_appendix": citations,
            "history_references": [str(narrative.get("history_summary") or "no history")],
            "state_constraints": [
                f"critical_publish_allowed={state.get('critical_publish_allowed')}",
                f"publish_scope={final_json.get('publish_scope')}",
                f"blocked_by={final_json.get('blocked_by') or []}",
            ],
            "data_quality_notes": list(final_json.get("data_quality_notes") or []),
        }
    ).model_dump(mode="json")


def _mock_final_article(
    final_json: dict[str, Any],
    judge: dict[str, Any],
    review: dict[str, Any],
    state: dict[str, Any],
    analyst_articles: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_ids = _unique(
        list(final_json.get("evidence_ids") or []) + _article_ids(analyst_articles)
    )
    primary_id = evidence_ids[0] if evidence_ids else "mock-evidence"
    article_citations = [
        citation
        for article in analyst_articles
        for citation in (article.get("evidence_citations") or [])
    ] or [{"evidence_id": primary_id, "note": "最终文章引用的主证据。"}]
    history_references = [
        ref
        for article in analyst_articles
        for ref in (article.get("history_references") or [])
    ]
    trend_frame = _build_final_trend_frame(
        analyst_articles=analyst_articles,
        evidence_rows=[
            citation
            for article in analyst_articles
            for citation in (
                article.get("data_source_appendix")
                or article.get("evidence_citations")
                or []
            )
        ],
        final_json=final_json,
        judge=judge,
    )
    return TypeAdapter(FinalObservationArticle).validate_python(
        {
            "title": "P4 最终观察与研究结论",
            "summary": (
                f"本轮最终状态为 trend_state={final_json.get('trend_state')}、"
                f"risk_state={final_json.get('risk_state')}、publish_allowed="
                f"{final_json.get('publish_allowed')}。主裁判共识为 "
                f"{judge.get('consensus_level')}，反方审查 passed={review.get('passed')}。"
            ),
            "trend_insight": _human_trend_summary(trend_frame, final_json),
            "marginal_change": str(trend_frame["marginal_change"]),
            "sensitive_signals": list(trend_frame["sensitive_signals"]),
            "early_warning_signals": list(trend_frame["strongest_signals"])[:5],
            "conflict_weighting": "; ".join(trend_frame["conflict_weighting"]),
            "scenario_map": list(trend_frame["scenario_map"]),
            "invalidation_conditions": list(trend_frame["invalidation_conditions"]),
            "watch_horizon": list(trend_frame["watch_horizon"]),
            "confidence_explanation": str(trend_frame["audit_constraints_summary"]),
            "audit_constraints_summary": str(trend_frame["audit_constraints_summary"]),
            "executive_summary": (
                f"最终控制器输出 publish_scope={final_json.get('publish_scope')}，"
                f"blocked_by={final_json.get('blocked_by') or []}。"
            ),
            "market_state": (
                f"trend_state={final_json.get('trend_state')}，"
                f"risk_state={final_json.get('risk_state')}。"
            ),
            "driver_analysis": "; ".join(
                str(item) for item in final_json.get("dominant_drivers") or []
            ),
            "conflict_analysis": "本轮反向证据由四个分析师 brief 与交叉质询共同约束。",
            "history_delta": "; ".join(history_references)[:1000],
            "event_watch": "; ".join(
                str(item) for item in final_json.get("invalidation_watch") or []
            ),
            "quality_and_runtime": _quality_readiness_text(final_json),
            "final_observation": (
                "本轮输出仅作为观察与审计结论，是否进入发布候选由 "
                "publish_allowed、publish_scope 与 blocked_by 共同决定。"
            ),
            "sections": [
                {
                    "heading": "综合状态",
                    "body": (
                        f"最终控制器 confidence={final_json.get('confidence')}，"
                        f"confidence_discount={final_json.get('confidence_discount')}。"
                        f"状态机 critical_publish_allowed={state.get('critical_publish_allowed')}。"
                    ),
                    "evidence_ids": [primary_id],
                },
                {
                    "heading": "分析师分歧与证据回链",
                    "body": "四个分析师文章均保留各自 evidence_id、历史记录和数据质量约束。",
                    "evidence_ids": evidence_ids[:12] or [primary_id],
                },
            ],
            "evidence_citations": article_citations,
            "data_source_appendix": [
                citation
                for article in analyst_articles
                for citation in (
                    article.get("data_source_appendix")
                    or article.get("evidence_citations")
                    or []
                )
            ]
            or article_citations,
            "analyst_article_titles": [
                str(article.get("title")) for article in analyst_articles if article.get("title")
            ],
            "history_references": history_references[:8],
            "state_constraints": [
                f"critical_publish_allowed={state.get('critical_publish_allowed')}",
                f"state_transition_allowed={state.get('state_transition_allowed')}",
                f"publish_scope={final_json.get('publish_scope')}",
                f"blocked_by={final_json.get('blocked_by') or []}",
            ],
            "data_quality_notes": list(final_json.get("data_quality_notes") or []),
            "publish_constraints": list(final_json.get("publish_constraints") or []),
        }
    ).model_dump(mode="json")


def _citation_from_evidence(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": row.get("evidence_id") or "unknown-evidence",
        "metric_id": row.get("metric_id"),
        "source_id": row.get("source_id"),
        "value": row.get("value"),
        "quality_score": row.get("quality_score"),
        "note": str(row.get("claim") or row.get("event_headline") or "evidence row"),
    }


def _evidence_rows_from_narrative(narrative: dict[str, Any]) -> list[dict[str, Any]]:
    rows = narrative.get("all_evidence") or narrative.get("top_evidence") or []
    return [row for row in rows if isinstance(row, dict)]


def _compact_evidence_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for row in rows:
        compact.append(
            {
                "evidence_id": row.get("evidence_id"),
                "module_id": row.get("module_id"),
                "metric_id": row.get("metric_id"),
                "source_id": row.get("source_id"),
                "value": row.get("value"),
                "quality_score": row.get("quality_score"),
                "direction": row.get("direction"),
                "strength": row.get("strength"),
                "role": row.get("role"),
                "claim": row.get("claim"),
                "history_available": row.get("history_available"),
            }
        )
    return compact


def _unique_evidence_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        evidence_id = row.get("evidence_id")
        key = str(evidence_id) if evidence_id else repr(row)
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def _ensure_article_evidence(
    article: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    output_model: type[AnalystReadableArticle] | type[FinalObservationArticle],
    appendix_heading: str,
) -> dict[str, Any]:
    expected_ids = _unique(
        [str(row["evidence_id"]) for row in evidence_rows if row.get("evidence_id")]
    )
    if not expected_ids:
        return article
    current_ids = set(_article_evidence_ids(article))
    missing_ids = [evidence_id for evidence_id in expected_ids if evidence_id not in current_ids]
    if missing_ids:
        article.setdefault("sections", []).append(
            {
                "heading": appendix_heading,
                "body": (
                    "This appendix preserves full Evidence Pack coverage for auditability. "
                    "The narrative may emphasize the strongest signals, while these "
                    "evidence_ids keep every assigned data point traceable."
                ),
                "evidence_ids": missing_ids,
            }
        )
    citation_ids = {
        str(item.get("evidence_id"))
        for item in article.get("evidence_citations") or []
        if item.get("evidence_id")
    }
    appendix_ids = {
        str(item.get("evidence_id"))
        for item in article.get("data_source_appendix") or []
        if item.get("evidence_id")
    }
    for row in evidence_rows:
        evidence_id = row.get("evidence_id")
        if evidence_id and str(evidence_id) not in citation_ids:
            citation = _citation_from_evidence(row)
            article.setdefault("evidence_citations", []).append(citation)
            citation_ids.add(str(evidence_id))
        if evidence_id and str(evidence_id) not in appendix_ids:
            article.setdefault("data_source_appendix", []).append(_citation_from_evidence(row))
            appendix_ids.add(str(evidence_id))
    return TypeAdapter(output_model).validate_python(article).model_dump(mode="json")


def _evidence_ids_from_narrative(narrative: dict[str, Any]) -> list[str]:
    evidence_ids = [
        str(row["evidence_id"])
        for row in _evidence_rows_from_narrative(narrative)
        if row.get("evidence_id")
    ]
    evidence_ids.extend(str(item) for item in narrative.get("coverage_target_evidence_ids") or [])
    for key in ("history_summary", "conclusion"):
        evidence_ids.extend(re.findall(r"ev-[A-Za-z0-9-]+", str(narrative.get(key) or "")))
    return _unique(evidence_ids) or ["mock-evidence"]


def _article_evidence_ids(article: dict[str, Any]) -> list[str]:
    ids = [str(item.get("evidence_id")) for item in article.get("evidence_citations") or []]
    for section in article.get("sections") or []:
        ids.extend(str(evidence_id) for evidence_id in section.get("evidence_ids") or [])
    return _unique([evidence_id for evidence_id in ids if evidence_id])


def _article_ids(articles: list[dict[str, Any]]) -> list[str]:
    return [
        evidence_id
        for article in articles
        for evidence_id in _article_evidence_ids(article)
    ]


def _history_reference_evidence_ids(articles: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for article in articles:
        for ref in article.get("history_references") or []:
            ids.extend(re.findall(r"ev-[A-Za-z0-9-]+", str(ref)))
    return _unique(ids)


def _publish_gate_summary(final_json: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    blocked_by = list(final_json.get("blocked_by") or [])
    return {
        "publish_allowed": bool(final_json.get("publish_allowed")),
        "publish_scope": final_json.get("publish_scope"),
        "watch_only": bool(final_json.get("watch_only")),
        "dashboard_only": bool(final_json.get("dashboard_only")),
        "publish_block_reason": final_json.get("publish_block_reason"),
        "blocked_by": blocked_by,
        "critical_publish_allowed": state.get("critical_publish_allowed"),
        "state_transition_allowed": state.get("state_transition_allowed"),
        "instruction": (
            "If blocked_by is non-empty or critical_publish_allowed is false, describe "
            "the run as observation-only/audit-only and state it does not enter formal "
            "publish_candidate."
        ),
    }


def _quality_readiness_summary(final_json: dict[str, Any]) -> dict[str, Any]:
    blocked_by = list(final_json.get("blocked_by") or [])
    fallback_reasons = [str(item) for item in final_json.get("fallback_reasons") or []]
    return {
        "data_quality_notes": list(final_json.get("data_quality_notes") or []),
        "confidence": final_json.get("confidence"),
        "confidence_discount": final_json.get("confidence_discount"),
        "llm_runtime_integrity": final_json.get("llm_runtime_integrity"),
        "fallback_used": bool(final_json.get("fallback_used")),
        "fallback_reason_count": len(fallback_reasons),
        "fallback_reason_summary": _summarize_runtime_reasons(fallback_reasons),
        "production_readiness": (
            "blocked"
            if "run_mode_integrity_invalidation" in blocked_by
            else ("constrained" if blocked_by else "eligible")
        ),
        "instruction": (
            "Separate Evidence Pack data quality from production readiness. A high "
            "data_quality_score can coexist with low production readiness when "
            "run-mode integrity, fallback, or hard constraints are active."
        ),
    }


def _article_safe_final_controller(final_json: dict[str, Any]) -> dict[str, Any]:
    payload = dict(final_json)
    fallback_reasons = [str(item) for item in payload.get("fallback_reasons") or []]
    failures = [str(item) for item in payload.get("agent_runtime_failures") or []]
    payload["fallback_reasons"] = _summarize_runtime_reasons(fallback_reasons)
    payload["agent_runtime_failures"] = _summarize_runtime_reasons(failures)
    payload["runtime_detail_policy"] = (
        "Article context carries short runtime summaries only. Full stack traces and "
        "raw provider errors stay in the audit appendix."
    )
    return payload


def _summarize_runtime_reasons(reasons: list[str], limit: int = 6) -> list[str]:
    summaries: list[str] = []
    for reason in reasons[:limit]:
        cleaned = re.sub(r"\s+", " ", reason).strip()
        if len(cleaned) > 220:
            cleaned = cleaned[:217].rstrip() + "..."
        summaries.append(cleaned)
    if len(reasons) > limit:
        summaries.append(f"{len(reasons) - limit} additional runtime issue(s) in audit appendix")
    return summaries


def _quality_readiness_text(final_json: dict[str, Any]) -> str:
    blocked_by = list(final_json.get("blocked_by") or [])
    quality_notes = "; ".join(str(item) for item in final_json.get("data_quality_notes") or [])
    readiness = _quality_readiness_summary(final_json)["production_readiness"]
    if readiness == "blocked":
        return (
            f"Evidence Pack data quality notes: {quality_notes or 'not available'}. "
            "Production readiness is blocked because run_mode_integrity_invalidation "
            "or equivalent hard constraints are active. High evidence-row quality does "
            "not make this run publishable; the output is observation/audit only. "
            f"blocked_by={blocked_by}."
        )
    if readiness == "constrained":
        return (
            f"Evidence Pack data quality notes: {quality_notes or 'not available'}. "
            f"Production readiness is constrained by blocked_by={blocked_by}; the "
            "output remains observation-level."
        )
    return (
        f"Evidence Pack data quality notes: {quality_notes or 'not available'}. "
        "No production publish hard block is present."
    )


def _analyst_id(narrative: dict[str, Any]) -> AnalystId:
    return TypeAdapter(AnalystId).validate_python(narrative.get("raw_analyst_id"))


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
