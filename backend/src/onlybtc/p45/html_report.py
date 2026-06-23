from __future__ import annotations

import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from sqlalchemy import select

from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID
from onlybtc.p45.final_writer import (
    P45_FINAL_ARTICLE_MODULE_ID,
    run_p45_final_writer,
)
from onlybtc.p45.llm_analyst_writer import P45_LLM_ANALYST_ARTICLES_MODULE_ID
from onlybtc.p45.llm_research_writer import P45_LLM_RESEARCH_ARTICLE_MODULE_ID
from onlybtc.p45.writer import P45_ANALYST_ARTICLES_MODULE_ID

P45_HTML_REPORT_FILENAME = "p45-research-report.html"


def run_p45_html_report(
    final_run_id: str | None = None,
    output_path: Path | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        final_payload = _load_payload(
            session=session,
            module_id=P45_FINAL_ARTICLE_MODULE_ID,
            run_id=final_run_id,
        )
        if final_payload is None:
            final_payload = run_p45_final_writer(db=db)

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
        llm_research_payload = _load_llm_research_payload(
            session=session,
            final_run_id=final_payload.get("final_run_id"),
        )
        llm_analyst_payload = _load_llm_analyst_payload(
            session=session,
            pack_id=final_payload.get("pack_id"),
        )

    if article_payload is None:
        raise RuntimeError("P4.5 analyst article payload is missing.")
    if pack_payload is None:
        raise RuntimeError("P4.5 evidence pack payload is missing.")

    report_path = output_path or paths.project_root / "reports" / P45_HTML_REPORT_FILENAME
    report_path.parent.mkdir(parents=True, exist_ok=True)
    html = _html_report(
        final_payload=final_payload,
        article_payload=article_payload,
        pack_payload=pack_payload,
        llm_research_payload=llm_research_payload,
        llm_analyst_payload=llm_analyst_payload,
    )
    report_path.write_text(html, encoding="utf-8")
    return {
        "status": "completed",
        "html_path": str(report_path),
        "final_run_id": final_payload.get("final_run_id"),
        "article_run_id": final_payload.get("article_run_id"),
        "pack_id": final_payload.get("pack_id"),
        "p3_run_id": final_payload.get("p3_run_id"),
        "p2_radar_run_id": final_payload.get("p2_radar_run_id"),
        "collect_run_id": final_payload.get("collect_run_id"),
        "llm_research_run_id": (llm_research_payload or {}).get("llm_research_run_id"),
        "llm_analyst_run_id": (llm_analyst_payload or {}).get("llm_analyst_run_id"),
    }


def _load_payload(
    session,
    module_id: str,
    run_id: str | None = None,
) -> dict[str, Any] | None:
    query = select(schema.ModuleJsonOutput).where(schema.ModuleJsonOutput.module_id == module_id)
    if run_id:
        query = query.where(schema.ModuleJsonOutput.run_id == run_id)
    row = session.scalar(query.order_by(schema.ModuleJsonOutput.created_at.desc()).limit(1))
    return dict(row.payload) if row else None


def _load_llm_research_payload(session, final_run_id: str | None) -> dict[str, Any] | None:
    rows = session.scalars(
        select(schema.ModuleJsonOutput)
        .where(schema.ModuleJsonOutput.module_id == P45_LLM_RESEARCH_ARTICLE_MODULE_ID)
        .order_by(schema.ModuleJsonOutput.created_at.desc())
        .limit(20)
    ).all()
    for row in rows:
        payload = dict(row.payload)
        if not final_run_id or payload.get("final_run_id") == final_run_id:
            return payload
    return None


def _load_llm_analyst_payload(session, pack_id: str | None) -> dict[str, Any] | None:
    rows = session.scalars(
        select(schema.ModuleJsonOutput)
        .where(schema.ModuleJsonOutput.module_id == P45_LLM_ANALYST_ARTICLES_MODULE_ID)
        .order_by(schema.ModuleJsonOutput.created_at.desc())
        .limit(20)
    ).all()
    for row in rows:
        payload = dict(row.payload)
        if not pack_id or payload.get("pack_id") == pack_id:
            return payload
    return None


def _html_report(
    final_payload: dict[str, Any],
    article_payload: dict[str, Any],
    pack_payload: dict[str, Any],
    llm_research_payload: dict[str, Any] | None = None,
    llm_analyst_payload: dict[str, Any] | None = None,
) -> str:
    evidence_rows = _flatten_evidence(pack_payload)
    module_rows = _flatten_modules(pack_payload)
    decision_card = final_payload.get("decision_card") or {}
    aggregation_audit = final_payload.get("aggregation_audit") or {}
    horizon_views = final_payload.get("horizon_views") or {}
    invalidation_rules = final_payload.get("invalidation_rules") or []
    confirmation_rules = final_payload.get("confirmation_rules") or []
    publish_article = final_payload.get("publish_article") or {}
    contract_validation = final_payload.get("contract_validation") or {}
    research_article = final_payload.get("research_article") or {}
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>P4.5 Research Report</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #07111a;
      --panel: #0d1f2d;
      --panel-2: #0a1823;
      --line: #1e3a4f;
      --text: #dbeafe;
      --muted: #93a4b8;
      --accent: #67e8f9;
      --good: #86efac;
      --bad: #fca5a5;
      --zero: #cbd5e1;
      --warn: #fde68a;
    }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: Arial, sans-serif; }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 28px; }}
    h1, h2, h3 {{ color: #f8fafc; letter-spacing: 0; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; }}
    h2 {{ margin-top: 30px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }}
    h3 {{ margin: 18px 0 8px; }}
    p, li {{ line-height: 1.65; }}
    a {{ color: var(--accent); text-decoration: none; }}
    code {{ color: #fef3c7; }}
    .muted {{ color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .card {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 14px;
    }}
    .card .label {{ color: #bae6fd; font-size: 13px; margin-bottom: 8px; }}
    .card .value {{
      color: var(--accent);
      font-size: 18px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }}
    .article {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 20px;
    }}
    .article p {{ margin: 10px 0; }}
    .pill {{
      display: inline-block;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 9px;
      margin: 2px 4px 2px 0;
    }}
    .bullish {{ color: var(--good); }}
    .bearish {{ color: var(--bad); }}
    .zero {{ color: var(--zero); }}
    .unavailable {{ color: var(--warn); }}
    .toolbar {{ margin: 12px 0; display: flex; flex-wrap: wrap; gap: 8px; }}
    .toolbar button {{
      background: var(--panel);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 7px 10px;
      cursor: pointer;
    }}
    .toolbar button:hover {{ border-color: var(--accent); }}
    .table-wrap {{
      width: 100%;
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{ width: 100%; border-collapse: collapse; min-width: 1320px; font-size: 13px; }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px;
      text-align: left;
      vertical-align: top;
      max-width: 260px;
      overflow-wrap: anywhere;
    }}
    th {{ color: #bae6fd; background: var(--panel-2); position: sticky; top: 0; z-index: 1; }}
    details {{
      border: 1px solid var(--line);
      background: var(--panel-2);
      border-radius: 8px;
      padding: 12px;
      margin-top: 12px;
    }}
    summary {{ cursor: pointer; color: #bae6fd; font-weight: 700; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; color: #d1d5db; }}
    @media (max-width: 960px) {{
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      main {{ padding: 18px; }}
    }}
    @media (max-width: 640px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
<main>
  <h1>P4.5 BTC 研究报告</h1>
  <p class="muted">生成时间：{escape(datetime.now(UTC).isoformat())}</p>
  <div class="grid">
    {_card("collect_run_id", final_payload.get("collect_run_id"))}
    {_card("p2_radar_run_id", final_payload.get("p2_radar_run_id"))}
    {_card("p3_run_id", final_payload.get("p3_run_id"))}
    {_card("final_run_id", final_payload.get("final_run_id"))}
    {_card("final_view", final_payload.get("final_view_cn") or final_payload.get("final_view"))}
    {_card(
        "legacy_core_view",
        final_payload.get("legacy_core_view") or final_payload.get("core_view"),
    )}
    {_card("direction", decision_card.get("direction_cn") or final_payload.get("final_view"))}
    {_card("strength", decision_card.get("strength_cn"))}
    {_card("confidence", _confidence_label(decision_card))}
    {_card("trade_permission", decision_card.get("trade_permission"))}
    {_card("article_run_id", final_payload.get("article_run_id"))}
    {_card("pack_id", final_payload.get("pack_id"))}
    {_card("runtime_mode", final_payload.get("runtime_mode"))}
  </div>

  <h2>决策卡</h2>
  {_decision_card_section(decision_card, contract_validation)}

  <h2>时间尺度拆分</h2>
  {_horizon_view_section(horizon_views)}

  <h2>反证条件</h2>
  {_table(_invalidation_headers(), _invalidation_rows(invalidation_rules))}

  <h2>偏空确认条件 / Confirmation Rules</h2>
  {_table(_invalidation_headers(), _invalidation_rows(confirmation_rules))}

  <h2>聚合逻辑审计</h2>
  {_aggregation_section(aggregation_audit)}

  <h2>最终综合研究文章</h2>
  <section class="article">
    {_render_article(research_article.get("body") or final_payload.get("article", ""))}
  </section>

  <h2>发文版本</h2>
  {_publish_article_section(publish_article)}

  <h2>四位分析员审计附录</h2>
  <p class="muted">
    以下为 deterministic 分析员审计附录，保留 evidence_id 和 fallback 细节，
    用于追溯输入，不作为最终发文版本。
  </p>
  {_analyst_articles(article_payload.get("analyst_articles", []))}

  <h2>Radar Module 总分</h2>
  {_table(_module_headers(), module_rows)}
  {_btc_total_state_section(final_payload, pack_payload)}
  {_options_volatility_section(final_payload, pack_payload)}
  {_event_policy_section(final_payload, pack_payload)}

  <h2>Evidence 附录</h2>
  <p class="muted">
    正文引用的 evidence_id 可以在这里对应到指标、来源、当前值、评分、
    语义规则和一句话说明。
  </p>
  <div class="toolbar">
    <button type="button" onclick="filterEvidence('all')">全部</button>
    <button type="button" onclick="filterEvidence('positive')">positive</button>
    <button type="button" onclick="filterEvidence('negative')">negative</button>
    <button type="button" onclick="filterEvidence('zero')">zero</button>
    <button type="button" onclick="filterEvidence('unavailable')">unavailable</button>
  </div>
  {_table(_evidence_headers(), evidence_rows, row_attr="score_bucket")}

  <details>
    <summary>Final JSON</summary>
    <pre>{escape(json.dumps(final_payload, ensure_ascii=False, indent=2))}</pre>
  </details>
  <details>
    <summary>Analyst JSON</summary>
    <pre>{escape(json.dumps(article_payload, ensure_ascii=False, indent=2))}</pre>
  </details>
  <details>
    <summary>Evidence Pack JSON</summary>
    <pre>{escape(json.dumps(pack_payload, ensure_ascii=False, indent=2))}</pre>
  </details>

  {_llm_research_section(llm_research_payload, final_payload)}
  {_llm_analyst_section(llm_analyst_payload)}
</main>
<script>
function filterEvidence(bucket) {{
  document.querySelectorAll('tr[data-score-bucket]').forEach(function(row) {{
    row.style.display = bucket === 'all' || row.dataset.scoreBucket === bucket ? '' : 'none';
  }});
}}
</script>
</body>
</html>
"""


def _llm_research_section(
    payload: dict[str, Any] | None,
    final_payload: dict[str, Any],
) -> str:
    if payload is None:
        return """
  <h2>LLM 深度中文研报</h2>
  <section class="article">
    <p class="muted">
      本 run 尚未生成 LLM Research Writer 研报；
      当前上方内容为 deterministic 可审计基线。
    </p>
  </section>
"""
    status = str(payload.get("status") or "unknown")
    meta = _table(
        ["key", "value"],
        [
            {"key": "llm_research_run_id", "value": payload.get("llm_research_run_id")},
            {"key": "llm_article_scope", "value": "internal_reference"},
            {"key": "participates_in_final_view", "value": False},
            {"key": "status", "value": status},
            {"key": "provider", "value": payload.get("provider")},
            {"key": "model", "value": payload.get("model")},
            {"key": "latency_ms", "value": payload.get("latency_ms")},
            {"key": "runtime_mode", "value": payload.get("runtime_mode")},
            {
                "key": "metric_evidence_count_seen",
                "value": payload.get("metric_evidence_count_seen"),
            },
            {"key": "created_at", "value": payload.get("created_at")},
            {"key": "error", "value": payload.get("error") or "-"},
        ],
    )
    article = (
        _render_article(payload.get("article", ""))
        if status == "completed"
        else f"<p>LLM Research Writer 未完成：{escape(str(payload.get('error') or '-'))}</p>"
    )
    conflict = _llm_view_conflict(payload, final_payload)
    conflict_html = (
        '<p class="unavailable"><strong>观点冲突提示：</strong>'
        "LLM 观点与量化聚合不一致，以下内容作为解释性参考，不作为最终决策。"
        "</p>"
        if conflict.get("llm_view_conflict")
        else ""
    )
    evidence = "".join(
        f'<a class="pill" href="#{escape(str(eid))}">{escape(str(eid))}</a>'
        for eid in payload.get("evidence_ids_used", [])
    )
    modules = ", ".join(str(item) for item in payload.get("radar_modules_covered", []))
    return f"""
  <h2>LLM 深度中文研报</h2>
  <details>
    <summary>LLM 深度中文研报 internal_reference</summary>
    <section class="article">
    <h3>{escape(str(payload.get("title") or "P4.5 LLM 深度中文研报"))}</h3>
    <p class="muted">
      llm_article_scope=internal_reference；该内容只作为内部解释参考，
      不参与 final_view，不作为发文版本。
    </p>
    {meta}
    {conflict_html}
    <p><strong>覆盖 Radar modules：</strong>{escape(modules or "-")}</p>
    {article}
    <p>{evidence}</p>
    </section>
  </details>
"""


def _confidence_label(decision_card: dict[str, Any]) -> str:
    confidence = decision_card.get("confidence")
    level = decision_card.get("confidence_level")
    if confidence is None and level is None:
        return "-"
    return f"{confidence} / {level}"


def _decision_card_section(decision: dict[str, Any], validation: dict[str, Any]) -> str:
    if not decision:
        return (
            '<section class="article"><p class="muted">'
            "当前 final payload 尚未包含 v2 decision_card。"
            "</p></section>"
        )
    rows = [
        {"key": "结论", "value": decision.get("conclusion_sentence")},
        {"key": "方向", "value": f"{decision.get('direction_cn')} ({decision.get('direction')})"},
        {"key": "强度", "value": f"{decision.get('strength_cn')} ({decision.get('strength')})"},
        {"key": "置信度", "value": _confidence_label(decision)},
        {"key": "交易许可", "value": decision.get("trade_permission")},
        {"key": "有效周期", "value": decision.get("valid_horizon")},
        {"key": "Contract", "value": validation.get("status", "-")},
    ]
    why = (
        decision.get("why_not_strong")
        or decision.get("why_not_strong_bearish")
        or decision.get("why_not_strong_bullish")
        or []
    )
    why_html = "".join(f"<li>{escape(str(item))}</li>" for item in why) or "<li>-</li>"
    return (
        '<section class="article">'
        f"{_table(['key', 'value'], rows)}"
        "<h3>为什么不是强单边</h3>"
        f"<ul>{why_html}</ul>"
        "</section>"
    )


def _horizon_view_section(horizons: dict[str, Any]) -> str:
    if not horizons:
        return (
            '<section class="article"><p class="muted">'
            "当前 final payload 尚未包含 horizon_views。"
            "</p></section>"
        )
    cards = []
    for key in ("h24", "d3", "d7"):
        item = horizons.get(key) or {}
        support = _driver_names(item.get("support_drivers", [])) or "-"
        pressure = _driver_names(item.get("pressure_drivers", [])) or "-"
        dominant = _driver_names(item.get("dominant_drivers", [])) or "-"
        rules = "".join(f"<li>{escape(str(rule))}</li>" for rule in item.get("watch_rules", []))
        cards.append(
            '<section class="card">'
            f"<h3>{escape(str(item.get('label') or key))}</h3>"
            f"<p><strong>方向：</strong>{escape(str(item.get('direction') or '-'))}；"
            f"<strong>强度：</strong>{escape(str(item.get('strength') or '-'))}；"
            f"<strong>置信度：</strong>{escape(str(item.get('confidence') or '-'))}</p>"
            f"<p><strong>支撑驱动：</strong>{escape(support)}</p>"
            f"<p><strong>压力驱动：</strong>{escape(pressure)}</p>"
            f"<p><strong>主导侧：</strong>{escape(str(item.get('dominant_side') or '-'))}；"
            f"<strong>主导驱动：</strong>{escape(dominant)}</p>"
            f"<p>{escape(str(item.get('interpretation') or '-'))}</p>"
            f"<ul>{rules}</ul>"
            "</section>"
        )
    return '<div class="grid">' + "\n".join(cards) + "</div>"


def _invalidation_headers() -> list[str]:
    return [
        "rule_id",
        "horizon",
        "title",
        "metric_ids",
        "applies_when",
        "operator",
        "conditions",
        "action_if_triggered",
        "reason",
    ]


def _invalidation_rows(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": item.get("rule_id"),
            "horizon": item.get("horizon"),
            "title": item.get("title"),
            "metric_ids": item.get("metric_ids"),
            "applies_when": ", ".join(str(value) for value in item.get("applies_when") or []),
            "operator": item.get("operator"),
            "conditions": _rule_conditions_text(item),
            "action_if_triggered": _rule_action_text(item.get("action_if_triggered") or {}),
            "reason": item.get("reason"),
        }
        for item in rules
    ]


def _rule_conditions_text(rule: dict[str, Any]) -> str:
    operator = str(rule.get("operator") or "AND")
    pieces = []
    for condition in rule.get("conditions") or []:
        if not isinstance(condition, dict):
            pieces.append(str(condition))
            continue
        metric = condition.get("metric_id") or "-"
        field = condition.get("field") or "value"
        op = condition.get("op") or "="
        value = condition.get("value")
        pieces.append(f"{metric}.{field} {op} {value}")
    return f" {operator} ".join(pieces) or "-"


def _rule_action_text(action: dict[str, Any]) -> str:
    if not action:
        return "-"
    text = f"{action.get('from', '-')} -> {action.get('to', '-')}"
    tag = action.get("tag")
    if tag:
        text += f" ({tag})"
    return text


def _aggregation_section(aggregation: dict[str, Any]) -> str:
    if not aggregation:
        return (
            '<section class="article"><p class="muted">'
            "当前 final payload 尚未包含 aggregation_audit。"
            "</p></section>"
        )
    summary_rows = [
        {"key": "directional_score", "value": aggregation.get("directional_score")},
        {"key": "raw_net_score", "value": aggregation.get("raw_net_score")},
        {"key": "direction", "value": aggregation.get("direction")},
        {"key": "strength", "value": aggregation.get("strength")},
        {"key": "strength_before_downgrade", "value": aggregation.get("strength_before_downgrade")},
        {"key": "downgrade_reasons", "value": aggregation.get("downgrade_reasons")},
        {"key": "confidence", "value": aggregation.get("confidence")},
        {"key": "disagreement_level", "value": aggregation.get("disagreement_level")},
        {"key": "data_quality_level", "value": aggregation.get("data_quality_level")},
        {"key": "zero_quality", "value": aggregation.get("zero_quality")},
        {"key": "score_components", "value": aggregation.get("score_components")},
        {"key": "score_normalization", "value": aggregation.get("score_normalization")},
    ]
    driver_headers = ["metric_id", "module", "direction", "weighted_contribution", "reason"]
    return (
        '<section class="article">'
        f"{_table(['key', 'value'], summary_rows)}"
        "<h3>支撑驱动</h3>"
        f"{_table(driver_headers, aggregation.get('support_drivers') or [])}"
        "<h3>压力驱动</h3>"
        f"{_table(driver_headers, aggregation.get('pressure_drivers') or [])}"
        "<h3>主导驱动</h3>"
        f"{_table(driver_headers, aggregation.get('dominant_drivers') or [])}"
        "</section>"
    )


def _publish_article_section(payload: dict[str, Any]) -> str:
    if not payload:
        return (
            '<section class="article"><p class="muted">'
            "当前 final payload 尚未包含 publish_article。"
            "</p></section>"
        )
    cashtags = ", ".join(str(item) for item in payload.get("cashtags", []))
    return (
        '<section class="article">'
        f"<h3>{escape(str(payload.get('title') or '-'))}</h3>"
        f"<p><strong>safe_to_publish：</strong>{escape(str(payload.get('safe_to_publish')))}</p>"
        f"{_render_article(payload.get('body', ''))}"
        f"<p><strong>cashtags：</strong>{escape(cashtags)}</p>"
        f"{_table(['key', 'value'], _dict_rows(payload.get('forbidden_content_check') or {}))}"
        "</section>"
    )


def _llm_analyst_section(payload: dict[str, Any] | None) -> str:
    if payload is None:
        return """
  <h2>四分析师 LLM 板块深度分析</h2>
  <section class="article">
    <p class="muted">
      本 run 尚未生成四分析师 LLM 板块深度分析。
    </p>
  </section>
"""
    meta = _table(
        ["key", "value"],
        [
            {"key": "llm_analyst_run_id", "value": payload.get("llm_analyst_run_id")},
            {"key": "provider", "value": payload.get("provider")},
            {"key": "runtime_mode", "value": payload.get("runtime_mode")},
            {"key": "created_at", "value": payload.get("created_at")},
            {"key": "total_latency_ms", "value": _analyst_total_latency(payload)},
            {"key": "summary", "value": payload.get("summary")},
        ],
    )
    cards = [meta]
    for item in payload.get("analyst_articles", []):
        status = item.get("status")
        article = (
            _render_article(item.get("article", ""))
            if status == "completed"
            else f"<p>分析师 LLM 未完成：{escape(str(item.get('error') or '-'))}</p>"
        )
        evidence = "".join(
            f'<a class="pill" href="#{escape(str(eid))}">{escape(str(eid))}</a>'
            for eid in item.get("evidence_ids_used", [])
        )
        modules = ", ".join(str(module) for module in item.get("radar_modules_covered", []))
        cards.append(
            '<section class="article">'
            f"<h3>{escape(str(item.get('title') or item.get('analyst_id') or '-'))}</h3>"
            f"<p><strong>status：</strong>{escape(str(status or '-'))}；"
            f"<strong>provider/model：</strong>{escape(str(item.get('provider') or '-'))}/"
            f"{escape(str(item.get('model') or '-'))}；"
            f"<strong>latency_ms：</strong>{escape(str(item.get('latency_ms') or 0))}；"
            f"<strong>error：</strong>{escape(str(item.get('error') or '-'))}；"
            "<strong>metric_seen：</strong>"
            f"{escape(str(item.get('metric_evidence_count_seen') or 0))}</p>"
            f"<p><strong>覆盖 Radar modules：</strong>{escape(modules or '-')}</p>"
            f"{article}"
            f"<p>{evidence}</p>"
            "</section>"
        )
    return "<h2>四分析师 LLM 板块深度分析</h2>\n" + "\n".join(cards)


def _analyst_total_latency(payload: dict[str, Any]) -> float:
    total = 0.0
    for item in payload.get("analyst_articles", []):
        try:
            total += float(item.get("latency_ms") or 0)
        except (TypeError, ValueError):
            continue
    return round(total, 3)


def _card(label: str, value: Any) -> str:
    return (
        '<div class="card">'
        f'<div class="label">{escape(label)}</div>'
        f'<div class="value">{escape(str(value or "-"))}</div>'
        "</div>"
    )


def _render_article(text: str) -> str:
    blocks = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# "):
            blocks.append(f"<h3>{escape(line[2:])}</h3>")
        elif line.startswith("## "):
            blocks.append(f"<h3>{escape(line[3:])}</h3>")
        elif line.startswith("- "):
            blocks.append(f"<p>{_link_evidence_ids(escape(line))}</p>")
        else:
            blocks.append(f"<p>{_link_evidence_ids(escape(line))}</p>")
    return "\n".join(blocks) if blocks else "<p>-</p>"


def _link_evidence_ids(text: str) -> str:
    # Evidence IDs are generated by the project and contain no HTML-sensitive
    # characters. The input text is already escaped before this replacement.
    parts = text.split()
    linked = []
    for part in parts:
        stripped = part.strip("，。；、:,;()（）")
        if stripped.startswith(("ev-", "p3-score-")):
            linked.append(part.replace(stripped, f'<a href="#{stripped}">{stripped}</a>'))
        else:
            linked.append(part)
    return " ".join(linked)


def _analyst_articles(articles: list[dict[str, Any]]) -> str:
    sections = []
    for item in articles:
        refs = [
            *_evidence_pills(item.get("key_positive_evidence_ids", []), "bullish"),
            *_evidence_pills(item.get("key_negative_evidence_ids", []), "bearish"),
            *_evidence_pills(item.get("neutral_watch_evidence_ids", []), "zero"),
        ]
        sections.append(
            "<details>"
            f"<summary>{escape(str(item.get('title', item.get('analyst_id', '-'))))}</summary>"
            '<section class="article">'
            f"<h3>{escape(str(item.get('title', item.get('analyst_id', '-'))))}</h3>"
            '<p class="muted">deterministic_analyst_audit_appendix</p>'
            f"<p><strong>方向：</strong>{escape(str(item.get('direction_view', '-')))}；"
            f"<strong>摘要：</strong>{escape(str(item.get('score_summary', '-')))}</p>"
            f"{_render_article(item.get('article', ''))}"
            f"<p>{''.join(refs)}</p>"
            "</section>"
            "</details>"
        )
    return "\n".join(sections) if sections else '<section class="article"><p>-</p></section>'


def _evidence_pills(evidence_ids: list[str], css_class: str) -> list[str]:
    return [
        f'<a class="pill {css_class}" href="#{escape(eid)}">{escape(eid)}</a>'
        for eid in evidence_ids
    ]


def _flatten_modules(pack_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for analyst in pack_payload.get("analysts", []):
        for module in analyst.get("modules", []):
            rows.append(
                {
                    "analyst_id": analyst.get("analyst_id"),
                    "radar_module": module.get("radar_module"),
                    "module_score": module.get("module_score"),
                    "module_effective_score": module.get("module_effective_score"),
                    "module_raw_score": module.get("module_raw_score"),
                    "module_final_score": module.get("module_final_score"),
                    "module_direction": module.get("module_direction"),
                    "module_effective_direction": module.get("module_effective_direction"),
                    "module_strength": module.get("module_strength"),
                    "module_confidence": module.get("module_confidence"),
                    "module_quality_score": module.get("module_quality_score"),
                    "coverage_score": module.get("coverage_score"),
                    "conflict_score": module.get("conflict_score"),
                    "freshness_factor": module.get("freshness_factor"),
                    "freshness_score": module.get("freshness_score"),
                    "raw_effective_conflict": module.get("raw_effective_conflict"),
                    "module_state": module.get("module_state"),
                    "direction_score": module.get("direction_score"),
                    "risk_score": module.get("risk_score"),
                    "confidence_score": module.get("confidence_score"),
                    "trend_state": module.get("trend_state"),
                    "trend_state_reason": module.get("trend_state_reason"),
                    "positioning_state": module.get("positioning_state"),
                    "top_positioning_state": module.get("top_positioning_state"),
                    "positioning_conflict_level": module.get("positioning_conflict_level"),
                    "long_short_squeeze_risk": module.get("long_short_squeeze_risk"),
                    "positive_metric_count": module.get("positive_metric_count"),
                    "negative_metric_count": module.get("negative_metric_count"),
                    "zero_metric_count": module.get("zero_metric_count"),
                    "unavailable_metric_count": module.get("unavailable_metric_count"),
                    "top_contributors": module.get("top_contributors"),
                    "module_explanation": module.get("module_explanation"),
                    "data_boundary": module.get("data_boundary"),
                }
            )
    return rows


def _flatten_evidence(pack_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for analyst in pack_payload.get("analysts", []):
        for module in analyst.get("modules", []):
            for metric in module.get("metrics", []):
                rows.append(
                    {
                        "evidence_id": metric.get("evidence_id"),
                        "analyst_id": analyst.get("analyst_id"),
                        "radar_module": module.get("radar_module"),
                        "metric_id": metric.get("metric_id"),
                        "source_id": metric.get("source_id"),
                        "value": metric.get("value"),
                        "metric_score": metric.get("metric_score"),
                        "metric_effective_score": metric.get("metric_effective_score"),
                        "base_metric_score": metric.get("base_metric_score"),
                        "score_bucket": metric.get("score_bucket"),
                        "direction": metric.get("direction"),
                        "base_direction": metric.get("base_direction"),
                        "positioning_signal": metric.get("positioning_signal"),
                        "crowding_contribution": metric.get("crowding_contribution"),
                        "positioning_scope": metric.get("positioning_scope"),
                        "quality_score": metric.get("quality_score"),
                        "freshness_weight": metric.get("freshness_weight"),
                        "horizon_weight": metric.get("horizon_weight"),
                        "duplicate_adjustment": metric.get("duplicate_adjustment"),
                        "horizon_tags": metric.get("horizon_tags"),
                        "duplicate_group_id": metric.get("duplicate_group_id"),
                        "semantic_rule_id": metric.get("semantic_rule_id"),
                        "semantic_warning": metric.get("semantic_warning"),
                        "p45_metric_brief": metric.get("p45_metric_brief"),
                        "score_reason": metric.get("score_reason"),
                    }
                )
    return rows


def _btc_total_state_section(
    final_payload: dict[str, Any],
    pack_payload: dict[str, Any],
) -> str:
    explanation = final_payload.get("btc_total_state_explanation")
    module = None
    for analyst in pack_payload.get("analysts", []):
        for item in analyst.get("modules", []):
            if item.get("radar_module") == "btc_total_state":
                module = item
                break
        if module:
            break
    if not isinstance(explanation, dict) or not explanation:
        explanation = _btc_total_explanation_from_module(module or {})
    if not explanation:
        return ""
    price = explanation.get("direction_drivers") or []
    risk = explanation.get("risk_drivers") or []
    rows = [
        {
            "layer": "short_term_direction",
            "state": explanation.get("btc_short_term_state"),
            "note": "price_state + perp_state composite only",
        }
    ]
    rows.extend(price)
    rows.extend(risk)
    rows.append(
        {
            "layer": "cycle_context",
            "state": ((explanation.get("cycle_context") or {}).get("state")),
            "note": "context only; not a 24h direction driver",
        }
    )
    rows.append(
        {
            "layer": "audit_context",
            "state": ((explanation.get("audit_context") or {}).get("state")),
            "note": "data audit only; not a direction driver",
        }
    )
    notes = "".join(
        f"<li>{escape(str(note))}</li>"
        for note in (
            (explanation.get("context_notes") or [])
            + (explanation.get("audit_notes") or [])
            + (explanation.get("composite_only_notes") or [])
        )
    )
    return (
        "<h2>BTC Total State v2 分层解释</h2>"
        '<section class="article">'
        f"{_table(['layer', 'state', 'risk_state', 'confirmation', 'note'], rows)}"
        f"<ul>{notes}</ul>"
        "</section>"
    )


def _btc_total_explanation_from_module(module: dict[str, Any]) -> dict[str, Any]:
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    price_state = pick("price_state")
    perp_state = pick("perp_state")
    return {
        "btc_short_term_state": pick("btc_short_term_state"),
        "direction_drivers": [
            {
                "layer": "price_state",
                "state": price_state.get("state") if isinstance(price_state, dict) else None,
            },
            {
                "layer": "perp_state",
                "state": perp_state.get("state") if isinstance(perp_state, dict) else None,
            },
        ],
        "risk_drivers": [
            {
                "layer": "perp_state",
                "state": perp_state.get("state") if isinstance(perp_state, dict) else None,
                "risk_state": perp_state.get("risk_state") if isinstance(perp_state, dict) else None,
                "confirmation": perp_state.get("confirmation") if isinstance(perp_state, dict) else None,
            }
        ],
        "cycle_context": pick("cycle_context"),
        "audit_context": pick("audit_context"),
        "context_notes": pick("context_notes") or [],
        "audit_notes": pick("audit_notes") or [],
        "composite_only_notes": [
            "Funding and OI are interpreted only together with price_state.",
            "Funding positive alone is not bullish; OI high alone is not directional.",
        ],
    }


def _options_volatility_section(final_payload: dict[str, Any], pack_payload: dict[str, Any]) -> str:
    explanation = final_payload.get("options_volatility_explanation")
    module = None
    for analyst in pack_payload.get("analysts", []):
        for item in analyst.get("modules", []):
            if item.get("radar_module") == "options_volatility":
                module = item
                break
        if module:
            break
    if not isinstance(explanation, dict) or not explanation:
        explanation = _options_explanation_from_module(module or {})
    if not explanation:
        return ""
    rows = [
        {
            "layer": "options_structure",
            "state": explanation.get("options_short_term_state"),
            "note": "risk and expiry structure only; not final direction",
        },
        {
            "layer": "volatility_pricing",
            "state": ((explanation.get("volatility_regime") or {}).get("state")),
            "note": "IV/RV and change context",
        },
        {
            "layer": "protection_demand",
            "state": ((explanation.get("protection_demand") or {}).get("state")),
            "note": "put-call and skew are not standalone bearish signals",
        },
        {
            "layer": "tail_risk",
            "state": ((explanation.get("tail_risk") or {}).get("state")),
            "note": "tail pricing context",
        },
        {
            "layer": "expiry_pressure",
            "state": ((explanation.get("expiry_pressure") or {}).get("state")),
            "note": "expiry pressure context",
        },
        {
            "layer": "pinning_structure",
            "state": ((explanation.get("pinning_structure") or {}).get("state")),
            "note": "max pain / gamma wall pinning context",
        },
    ]
    notes = "".join(
        f"<li>{escape(str(note))}</li>"
        for note in (explanation.get("context_notes") or [])
    )
    return (
        "<h2>Options Volatility v2.1 风险结构解释</h2>"
        '<section class="article">'
        f"<p>trade_permission_hint: {escape(str(explanation.get('trade_permission_hint') or 'normal'))}</p>"
        f"{_table(['layer', 'state', 'note'], rows)}"
        f"<ul>{notes}</ul>"
        "</section>"
    )


def _options_explanation_from_module(module: dict[str, Any]) -> dict[str, Any]:
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "options_short_term_state": pick("options_short_term_state"),
        "trade_permission_hint": pick("trade_permission_hint"),
        "volatility_regime": pick("volatility_regime"),
        "protection_demand": pick("protection_demand"),
        "tail_risk": pick("tail_risk"),
        "expiry_pressure": pick("expiry_pressure"),
        "pinning_structure": pick("pinning_structure"),
        "context_notes": pick("context_notes") or [
            "Options volatility is not a directional alpha module.",
        ],
    }


def _event_policy_section(final_payload: dict[str, Any], pack_payload: dict[str, Any]) -> str:
    explanation = final_payload.get("event_policy_explanation")
    module = None
    for analyst in pack_payload.get("analysts", []):
        for item in analyst.get("modules", []):
            if item.get("radar_module") == "event_policy":
                module = item
                break
        if module:
            break
    if not isinstance(explanation, dict) or not explanation:
        explanation = _event_policy_explanation_from_module(module or {})
    if not explanation:
        return ""
    trade_gate = explanation.get("trade_gate") or {}
    rows = [
        {
            "layer": "event_gate",
            "state": explanation.get("event_short_term_state"),
            "note": "event timing gate only; not final direction",
        },
        {
            "layer": "dominant_event",
            "state": explanation.get("dominant_event_type"),
            "note": f"phase={explanation.get('event_window_phase')}",
        },
        {
            "layer": "nearest_event",
            "state": explanation.get("nearest_event_type"),
            "note": f"hours={explanation.get('nearest_event_hours')}",
        },
        {
            "layer": "trade_gate",
            "state": trade_gate.get("reason_code"),
            "note": f"size_multiplier={trade_gate.get('position_size_multiplier')}",
        },
        {
            "layer": "breakout_permission",
            "state": trade_gate.get("allow_breakout_entry"),
            "note": "false breakouts are discounted inside event windows",
        },
    ]
    notes = "".join(
        f"<li>{escape(str(note))}</li>"
        for note in (explanation.get("context_notes") or [])
    )
    return (
        "<h2>Event Policy v2.1 浜嬩欢椋庨櫓闂ㄦ帶</h2>"
        '<section class="article">'
        f"<p>{escape(str(explanation.get('summary') or 'Event policy is neutral.'))}</p>"
        f"{_table(['layer', 'state', 'note'], rows)}"
        f"<ul>{notes}</ul>"
        "</section>"
    )


def _event_policy_explanation_from_module(module: dict[str, Any]) -> dict[str, Any]:
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "event_short_term_state": pick("event_short_term_state"),
        "dominant_event_type": pick("dominant_event_type"),
        "nearest_event_type": pick("nearest_event_type"),
        "nearest_event_hours": pick("nearest_event_hours"),
        "event_window_phase": pick("event_window_phase"),
        "trade_gate": pick("trade_gate"),
        "context_notes": pick("context_notes") or [
            "Event policy is not a directional alpha module.",
        ],
        "summary": pick("summary"),
    }


def _module_headers() -> list[str]:
    return [
        "analyst_id",
        "radar_module",
        "module_score",
        "module_effective_score",
        "module_raw_score",
        "module_final_score",
        "module_direction",
        "module_effective_direction",
        "module_strength",
        "module_confidence",
        "module_quality_score",
        "coverage_score",
        "conflict_score",
        "freshness_factor",
        "freshness_score",
        "raw_effective_conflict",
        "module_state",
        "direction_score",
        "risk_score",
        "confidence_score",
        "trend_state",
        "trend_state_reason",
        "positioning_state",
        "top_positioning_state",
        "positioning_conflict_level",
        "long_short_squeeze_risk",
        "positive_metric_count",
        "negative_metric_count",
        "zero_metric_count",
        "unavailable_metric_count",
        "top_contributors",
        "module_explanation",
        "data_boundary",
    ]


def _evidence_headers() -> list[str]:
    return [
        "evidence_id",
        "analyst_id",
        "radar_module",
        "metric_id",
        "source_id",
        "value",
        "metric_score",
        "metric_effective_score",
        "base_metric_score",
        "score_bucket",
        "direction",
        "base_direction",
        "positioning_signal",
        "crowding_contribution",
        "positioning_scope",
        "quality_score",
        "freshness_weight",
        "horizon_weight",
        "duplicate_adjustment",
        "horizon_tags",
        "duplicate_group_id",
        "semantic_rule_id",
        "semantic_warning",
        "p45_metric_brief",
        "score_reason",
    ]


def _table(
    headers: list[str],
    rows: list[dict[str, Any]],
    row_attr: str | None = None,
) -> str:
    if not rows:
        rows = [{header: "-" for header in headers}]
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body = []
    for row in rows:
        attrs = ""
        if row_attr:
            value = escape(str(row.get(row_attr, "")))
            attrs = f' data-score-bucket="{value}"'
        cells = "".join(
            f"<td>{_format_cell(header, row.get(header, ''))}</td>" for header in headers
        )
        body.append(f"<tr{attrs}>{cells}</tr>")
    return (
        '<div class="table-wrap">'
        f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"
        "</div>"
    )


def _format_cell(header: str, value: Any) -> str:
    if header == "evidence_id" and value:
        escaped = escape(str(value))
        return f'<span id="{escaped}">{escaped}</span>'
    if isinstance(value, list):
        return escape(", ".join(str(item) for item in value) or "-")
    if isinstance(value, dict):
        return escape(json.dumps(value, ensure_ascii=False, sort_keys=True))
    if isinstance(value, float):
        return escape(str(round(value, 6)))
    return escape(str(value if value is not None and value != "" else "-"))


def _dict_rows(values: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"key": key, "value": value} for key, value in values.items()]


def _driver_names(drivers: list[dict[str, Any]]) -> str:
    return ", ".join(str(item.get("metric_id")) for item in drivers if item.get("metric_id"))


def _llm_view_conflict(
    payload: dict[str, Any],
    final_payload: dict[str, Any],
) -> dict[str, Any]:
    final_view = str(final_payload.get("final_view") or "neutral")
    article = str(payload.get("article") or "").lower()
    llm_view = "neutral"
    if "核心观点：偏空" in article or "bearish" in article or "偏空" in article[:500]:
        llm_view = "bearish"
    elif "核心观点：偏多" in article or "bullish" in article or "偏多" in article[:500]:
        llm_view = "bullish"
    conflict = llm_view != "neutral" and final_view != llm_view
    return {
        "llm_view_conflict": conflict,
        "llm_view": llm_view,
        "canonical_final_view": final_view,
    }
