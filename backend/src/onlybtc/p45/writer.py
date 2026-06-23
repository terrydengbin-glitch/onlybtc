from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p45.evidence_pack import (
    P45_EVIDENCE_PACK_MODULE_ID,
    build_p45_scored_evidence_pack,
)

P45_ANALYST_ARTICLES_MODULE_ID = "p45_analyst_articles"
P45_ANALYST_ARTICLES_SCHEMA_VERSION = "p45.analyst_articles.v1"

ANALYST_TITLES = {
    "macro_event_analyst": "宏观与事件分析员",
    "liquidity_flow_analyst": "流动性与资金流分析员",
    "microstructure_analyst": "微观结构分析员",
    "onchain_structure_analyst": "链上结构分析员",
}

ANALYST_PROMPT_FRAMES = {
    "macro_event_analyst": "关注美元、利率、风险偏好、亚洲风险和宏观事件窗口。",
    "liquidity_flow_analyst": "关注美元流动性、ETF、稳定币和市场宽度。",
    "microstructure_analyst": "关注价格动能、成交、衍生品拥挤、清算和期权保护需求。",
    "onchain_structure_analyst": "关注 BTC 内生状态、采用度、链上估值和成本基础。",
}


def run_p45_analyst_writers(
    pack_id: str | None = None,
    article_run_id: str | None = None,
    runtime_mode: str = "deterministic",
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        pack = _load_pack(session, pack_id)
        if pack is None:
            pack = build_p45_scored_evidence_pack(db=db)
        article_run_id = article_run_id or _generate_article_run_id()
        analyst_articles = [
            _write_analyst_article(analyst, runtime_mode)
            for analyst in pack["analysts"]
        ]
        result = {
            "schema_version": P45_ANALYST_ARTICLES_SCHEMA_VERSION,
            "article_run_id": article_run_id,
            "pack_id": pack["pack_id"],
            "p3_run_id": pack.get("p3_run_id"),
            "p2_radar_run_id": pack.get("p2_radar_run_id"),
            "collect_run_id": pack.get("collect_run_id"),
            "runtime_mode": runtime_mode,
            "created_at": datetime.now(UTC).isoformat(),
            "prompt_frames": ANALYST_PROMPT_FRAMES,
            "analyst_articles": analyst_articles,
            "summary": {
                "analyst_count": len(analyst_articles),
                "all_reference_evidence": all(
                    item["evidence_reference_count"] > 0 for item in analyst_articles
                ),
                "fallback_used": runtime_mode != "llm",
            },
        }
        session.add(
            schema.ModuleJsonOutput(
                run_id=article_run_id,
                module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                schema_version=P45_ANALYST_ARTICLES_SCHEMA_VERSION,
                payload=result,
            )
        )
        return result


def _write_analyst_article(analyst: dict[str, Any], runtime_mode: str) -> dict[str, Any]:
    metrics = [
        metric
        for module in analyst.get("modules", [])
        for metric in module.get("metrics", [])
    ]
    positive = _top_metrics(metrics, "positive", reverse=True)
    negative = _top_metrics(metrics, "negative", reverse=False)
    zero = [item for item in metrics if item.get("score_bucket") == "zero"]
    unavailable = [item for item in metrics if item.get("score_bucket") == "unavailable"]
    direction_view = _direction_view(analyst)
    evidence_ids = [
        item.get("evidence_id")
        for item in [*positive[:3], *negative[:3], *zero[:2], *unavailable[:2]]
        if item.get("evidence_id")
    ]
    role_title = ANALYST_TITLES.get(analyst["analyst_id"], analyst["analyst_id"])
    title = f"{role_title}：{_direction_cn(direction_view)}"
    article = _article_text(
        analyst=analyst,
        direction_view=direction_view,
        positive=positive,
        negative=negative,
        zero=zero,
        unavailable=unavailable,
        evidence_ids=evidence_ids,
        runtime_mode=runtime_mode,
    )
    return {
        "analyst_id": analyst["analyst_id"],
        "title": title,
        "direction_view": direction_view,
        "score_summary": (
            f"模块 {analyst['module_count']} 个，指标 {analyst['metric_count']} 个；"
            f"正分 {analyst['positive']}，负分 {analyst['negative']}，"
            f"零分 {analyst['zero']}，不可用 {analyst['unavailable']}。"
        ),
        "article": article,
        "key_positive_evidence_ids": [
            item["evidence_id"] for item in positive[:5] if item.get("evidence_id")
        ],
        "key_negative_evidence_ids": [
            item["evidence_id"] for item in negative[:5] if item.get("evidence_id")
        ],
        "neutral_watch_evidence_ids": [
            item["evidence_id"] for item in zero[:5] if item.get("evidence_id")
        ],
        "watch_items": _watch_items(positive, negative, zero, unavailable),
        "data_boundary": analyst.get("data_boundary", []),
        "evidence_reference_count": len(evidence_ids),
        "runtime_mode": runtime_mode,
        "fallback_used": runtime_mode != "llm",
        "prompt_frame": ANALYST_PROMPT_FRAMES.get(analyst["analyst_id"], ""),
    }


def _article_text(
    analyst: dict[str, Any],
    direction_view: str,
    positive: list[dict[str, Any]],
    negative: list[dict[str, Any]],
    zero: list[dict[str, Any]],
    unavailable: list[dict[str, Any]],
    evidence_ids: list[str],
    runtime_mode: str,
) -> str:
    role = ANALYST_TITLES.get(analyst["analyst_id"], analyst["analyst_id"])
    frame = ANALYST_PROMPT_FRAMES.get(analyst["analyst_id"], "")
    parts = [
        f"{role}本轮覆盖 {', '.join(analyst['radar_modules'])}。{frame}",
        (
            f"综合方向为{_direction_cn(direction_view)}：正分 {analyst['positive']} 项、"
            f"负分 {analyst['negative']} 项、零分 {analyst['zero']} 项、"
            f"不可用 {analyst['unavailable']} 项。"
        ),
    ]
    if positive:
        parts.append(
            "主要正向证据："
            + "；".join(_metric_sentence(item) for item in positive[:3])
            + "。"
        )
    if negative:
        parts.append(
            "主要负向证据："
            + "；".join(_metric_sentence(item) for item in negative[:3])
            + "。"
        )
    if zero:
        parts.append(
            "中性观察项："
            + "；".join(_metric_sentence(item) for item in zero[:3])
            + "。这些指标当前不直接贡献方向，但可作为后续验证路径。"
        )
    if unavailable:
        parts.append(
            "数据边界："
            + "；".join(item.get("metric_id", "") for item in unavailable[:4])
            + " 暂不可用，已从方向评分中剔除。"
        )
    parts.append(
        "需要重点观察的是正负证据是否继续同向扩散，或被零分观察项重新触发。"
        f"本文引用 evidence_id：{', '.join(evidence_ids[:10])}。"
    )
    if runtime_mode != "llm":
        parts.append("当前为 deterministic fallback 输出，后续可由 LLM 在同一证据框架下扩写。")
    return "\n\n".join(parts)


def _top_metrics(
    metrics: list[dict[str, Any]], bucket: str, reverse: bool
) -> list[dict[str, Any]]:
    return sorted(
        [item for item in metrics if item.get("score_bucket") == bucket],
        key=lambda item: float(item.get("metric_score") or 0.0),
        reverse=reverse,
    )


def _direction_view(analyst: dict[str, Any]) -> str:
    score = 0.0
    for module in analyst.get("modules", []):
        score += float(module.get("module_score") or 0.0)
    if score > 0.12:
        return "bullish"
    if score < -0.12:
        return "bearish"
    if analyst.get("positive") and analyst.get("negative"):
        return "mixed"
    return "neutral"


def _direction_cn(value: str) -> str:
    return {
        "bullish": "偏多",
        "bearish": "偏空",
        "mixed": "分歧",
        "neutral": "中性观察",
    }.get(value, value)


def _metric_sentence(item: dict[str, Any]) -> str:
    return (
        f"{item.get('metric_id')}({item.get('evidence_id')}) 分数={item.get('metric_score')}，"
        f"{item.get('p45_metric_brief') or item.get('score_reason')}"
    )


def _watch_items(
    positive: list[dict[str, Any]],
    negative: list[dict[str, Any]],
    zero: list[dict[str, Any]],
    unavailable: list[dict[str, Any]],
) -> list[str]:
    return [
        *[f"确认正向证据是否延续：{item.get('metric_id')}" for item in positive[:2]],
        *[f"监控负向压力是否扩大：{item.get('metric_id')}" for item in negative[:2]],
        *[f"观察中性项是否转向：{item.get('metric_id')}" for item in zero[:2]],
        *[f"数据边界等待补齐：{item.get('metric_id')}" for item in unavailable[:2]],
    ]


def _load_pack(session, pack_id: str | None) -> dict[str, Any] | None:
    query = select(schema.ModuleJsonOutput).where(
        schema.ModuleJsonOutput.module_id == P45_EVIDENCE_PACK_MODULE_ID
    )
    if pack_id:
        query = query.where(schema.ModuleJsonOutput.run_id == pack_id)
    row = session.scalar(query.order_by(schema.ModuleJsonOutput.created_at.desc()).limit(1))
    return dict(row.payload) if row else None


def _generate_article_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"p45articles-{stamp}-{uuid4().hex[:6]}"
