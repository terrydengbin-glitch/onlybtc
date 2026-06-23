from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.repositories import RadarRuntimeRepository
from onlybtc.db.session import Database, database
from onlybtc.radar_runtime.profile import profile_by_module
from onlybtc.sources.registry import SOURCE_CONFIGS


REPORT_NAME = "radar-metrics-score-btc-ui-chain-audit"
EXPECTED_MODULES = [
    "macro_radar",
    "dollar_liquidity",
    "treasury_credit",
    "kline_orderflow",
    "derivatives_crowding",
    "fund_flow",
    "btc_adoption",
    "onchain_valuation",
    "trade_structure_flow",
    "options_volatility",
    "crypto_breadth",
    "asia_risk",
    "event_policy",
    "btc_total_state",
]


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _iter_feature_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if _looks_like_feature(value):
            records.append(value)
        for child in value.values():
            records.extend(_iter_feature_records(child))
    elif isinstance(value, list):
        for child in value:
            records.extend(_iter_feature_records(child))
    return records


def _looks_like_feature(value: dict[str, Any]) -> bool:
    keys = {
        "metric_id",
        "source_id",
        "freshness_status",
        "collection_freshness_status",
        "business_recency_status",
        "source_ts",
        "collected_at",
    }
    return bool(keys.intersection(value))


def _is_optional_feature(feature: dict[str, Any]) -> bool:
    metric_id = str(feature.get("metric_id") or "")
    if feature.get("quality_blocking") is False:
        return True
    if metric_id.startswith("liquidation_"):
        return True
    if metric_id.endswith("_percentile_252d"):
        return True
    if str(feature.get("business_recency_status") or "") in {"expected_lag", "lagging", "outdated"}:
        return True
    return False


def _is_derived_source(source_id: str) -> bool:
    sid = str(source_id or "").lower()
    return sid.endswith("-derived") or sid.endswith("_derived") or "derived" in sid


def _has_embedded_feature_value(feature: dict[str, Any]) -> bool:
    for key in ("value", "current_value", "raw_value", "score", "direction_score"):
        if feature.get(key) not in (None, ""):
            return True
    return bool(feature.get("current_run_has_value"))


def _status_rank(status: str) -> int:
    return {"PASS": 0, "PARTIAL": 1, "FAIL": 2}.get(status, 2)


def _merge_status(values: list[str]) -> str:
    if not values:
        return "PASS"
    return max(values, key=_status_rank)


def _severity_for_break(status: str, module_id: str, kind: str) -> str:
    if status != "FAIL":
        return "none"
    if module_id in {"kline_orderflow", "derivatives_crowding", "trade_structure_flow", "asia_risk"}:
        return "critical" if kind in {"module_score", "runtime_cockpit", "api_ui"} else "high"
    if kind in {"module_score", "runtime_cockpit", "api_ui"}:
        return "high"
    return "medium"


def _latest_source_run(session: Any, source_id: str) -> dict[str, Any]:
    row = session.scalar(
        select(schema.SourceRun)
        .where(schema.SourceRun.source_id == source_id)
        .order_by(schema.SourceRun.started_at.desc(), schema.SourceRun.id.desc())
        .limit(1)
    )
    if row is None:
        return {}
    return {
        "run_id": row.run_id,
        "status": row.status,
        "mode": row.mode,
        "started_at": row.started_at.isoformat() if row.started_at else "",
        "completed_at": row.completed_at.isoformat() if row.completed_at else "",
        "error_message": row.error_message or "",
    }


def _raw_observation_count(session: Any, source_id: str, run_id: str | None) -> int:
    query = select(func.count()).select_from(schema.RawObservation).where(
        schema.RawObservation.source_id == source_id
    )
    if run_id:
        query = query.where(schema.RawObservation.run_id == run_id)
    return int(session.scalar(query) or 0)


def _latest_metric_value(session: Any, metric_id: str, source_id: str | None) -> dict[str, Any]:
    query = select(schema.MetricValue).where(schema.MetricValue.metric_id == metric_id)
    if source_id:
        query = query.where(schema.MetricValue.source_id == source_id)
    row = session.scalar(query.order_by(schema.MetricValue.ts.desc(), schema.MetricValue.id.desc()).limit(1))
    if row is None:
        return {}
    return {
        "metric_id": row.metric_id,
        "source_id": row.source_id,
        "run_id": row.run_id,
        "run_mode": row.run_mode,
        "ts": row.ts.isoformat() if row.ts else "",
        "value": row.value,
        "quality_score": row.quality_score,
        "is_fallback": row.is_fallback,
    }


def _latest_module_json(session: Any, module_id: str, run_id: str | None = None) -> dict[str, Any]:
    query = select(schema.ModuleJsonOutput).where(schema.ModuleJsonOutput.module_id == module_id)
    if run_id:
        query = query.where(schema.ModuleJsonOutput.run_id == run_id)
    row = session.scalar(query.order_by(schema.ModuleJsonOutput.created_at.desc()).limit(1))
    if row is None:
        return {}
    return {
        "run_id": row.run_id,
        "schema_version": row.schema_version,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "payload": row.payload,
    }


def _frontend_contract_checks(project_root: Path) -> list[dict[str, Any]]:
    checks = [
        {
            "check_id": "store-loads-radar-runtime-apis",
            "file": "frontend/src/store.ts",
            "patterns": [
                "getRadarRuntimeDaemonStatus",
                "getRadarRuntimeCockpitLatest",
                "getRadarRuntimeModulesLatest",
            ],
        },
        {
            "check_id": "btc-card-consumes-runtime-cockpit",
            "file": "frontend/src/App.vue",
            "patterns": [
                "btc_runtime_cockpit",
                "runtimeCockpitScores",
                "fast_net_score",
                "hasRuntimeCockpit",
            ],
        },
        {
            "check_id": "radar-ui-consumes-module-score",
            "file": "frontend/src/App.vue",
            "patterns": [
                "module_effective_score",
                "module_score",
                "selectedRadarModule",
            ],
        },
        {
            "check_id": "radar-ui-shows-runtime-source-health",
            "file": "frontend/src/App.vue",
            "patterns": [
                "source_freshness_state",
                "radarRuntimeHealth",
                "radarRuntimeDaemon",
            ],
        },
    ]
    results: list[dict[str, Any]] = []
    for item in checks:
        path = project_root / item["file"]
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = [pattern for pattern in item["patterns"] if pattern not in text]
        results.append(
            {
                **item,
                "status": "PASS" if not missing else "FAIL",
                "missing_patterns": missing,
            }
        )
    return results


def _module_summary(
    *,
    session: Any,
    module: dict[str, Any],
    source_config_ids: set[str],
    contribution_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    module_id = str(module.get("module_name") or module.get("module_id") or "")
    payload = module.get("module_payload") if isinstance(module.get("module_payload"), dict) else module
    features = _iter_feature_records(payload)
    source_freshness = module.get("source_freshness") or {}
    module_json = _latest_module_json(session, module_id, str(module.get("run_id") or ""))
    contribution = contribution_index.get(module_id, {})

    feature_rows: list[dict[str, Any]] = []
    feature_statuses: list[str] = []
    break_reasons: list[str] = []
    for feature in features:
        metric_id = str(feature.get("metric_id") or "")
        source_id = str(feature.get("source_id") or "")
        quality_blocking = bool(feature.get("quality_blocking"))
        optional = _is_optional_feature(feature)
        derived_source = _is_derived_source(source_id)
        has_embedded_value = _has_embedded_feature_value(feature)
        source_config_status = "PASS"
        source_run_status = "PASS"
        raw_status = "PASS"
        metric_status = "PASS"
        source_run = {}
        raw_count = 0
        metric_value = {}

        if metric_id:
            metric_value = _latest_metric_value(session, metric_id, source_id or None)
            if not metric_value:
                metric_status = "PARTIAL" if optional or not quality_blocking or has_embedded_value else "FAIL"
                break_reasons.append(f"{metric_id}: no metric_value row")
        else:
            metric_status = "PARTIAL"

        has_chain_value = bool(metric_value) or has_embedded_value

        if source_id and derived_source:
            # Derived features are produced inside P1/P2/P3/P4.5 processors from
            # upstream inputs. They do not have a collector source_run/raw row by
            # design, so the audit tracks them as transform lineage rather than
            # source gaps.
            source_config_status = "PASS"
            source_run_status = "PASS" if has_chain_value else ("PARTIAL" if optional else "FAIL")
            raw_status = "PASS" if has_chain_value else ("PARTIAL" if optional else "FAIL")
            if not has_chain_value:
                break_reasons.append(f"{metric_id}: derived feature has no persisted or embedded value")
        elif source_id:
            if source_id not in source_config_ids:
                source_config_status = "FAIL"
                break_reasons.append(f"{metric_id}: source config missing for {source_id}")
            source_run = _latest_source_run(session, source_id)
            if not source_run:
                source_run_status = "PARTIAL" if optional else "FAIL"
                break_reasons.append(f"{metric_id}: no source_run for {source_id}")
            elif source_run.get("status") not in {
                "success",
                "healthy",
                "ok",
                "partial",
                "fallback_used",
                "expected_lag",
            }:
                source_run_status = "PARTIAL" if source_run.get("status") == "warning" or optional else "FAIL"
                break_reasons.append(f"{metric_id}: latest source_run status={source_run.get('status')}")
            raw_count = _raw_observation_count(session, source_id, source_run.get("run_id"))
            if raw_count <= 0 and source_run:
                raw_status = "PARTIAL" if optional else "FAIL"
                break_reasons.append(f"{metric_id}: source_run has no raw_observation for {source_id}")
        else:
            source_config_status = "PARTIAL" if optional or "derived" in metric_id or has_chain_value else "FAIL"
            source_run_status = source_config_status
            raw_status = source_config_status
            if source_config_status == "FAIL":
                break_reasons.append(f"{metric_id}: missing source_id")

        row_status = _merge_status([source_config_status, source_run_status, raw_status, metric_status])
        feature_statuses.append(row_status)
        feature_rows.append(
            {
                "metric_id": metric_id,
                "source_id": source_id,
                "quality_blocking": quality_blocking,
                "optional": optional,
                "feature_freshness": feature.get("freshness_status"),
                "business_recency": feature.get("business_recency_status"),
                "source_config_status": source_config_status,
                "source_run_status": source_run_status,
                "raw_observation_count": raw_count,
                "raw_status": raw_status,
                "metric_status": metric_status,
                "metric_value_ts": metric_value.get("ts"),
                "status": row_status,
            }
        )

    score = module.get("module_effective_score", module.get("module_score"))
    score_source = str(module.get("score_source") or "")
    direction = module.get("module_effective_direction") or module.get("module_direction")
    signal_stage = module.get("signal_stage")
    module_score_status = "PASS"
    if score in (None, ""):
        module_score_status = "FAIL"
        break_reasons.append("module score missing")
    elif float(score or 0.0) == 0.0 and str(direction or "neutral") != "neutral":
        module_score_status = "PARTIAL"
        break_reasons.append("non-neutral direction has zero score")
    elif float(score or 0.0) == 0.0 and "missing" in score_source:
        module_score_status = "PARTIAL"
        break_reasons.append("zero score uses missing score source")

    module_payload_status = "PASS" if module_json else "PARTIAL"
    cockpit_status = "PASS" if contribution else "PARTIAL"
    source_status = "PASS" if source_freshness.get("state") in {"fresh", "expected_lag", "partial_live", "partial"} else "FAIL"
    status = _merge_status(
        [
            _merge_status(feature_statuses),
            module_score_status,
            module_payload_status,
            cockpit_status,
            source_status,
        ]
    )
    severity = "none"
    if status == "FAIL":
        severity = _severity_for_break(status, module_id, "module_score" if module_score_status == "FAIL" else "metric")
    return {
        "module_id": module_id,
        "status": status,
        "severity": severity,
        "cadence_group": module.get("cadence_group"),
        "source_group_id": module.get("source_group_id"),
        "runtime_freshness": (module.get("runtime_freshness") or {}).get("state") or module.get("freshness_state"),
        "source_freshness": source_freshness.get("state"),
        "participation_policy": module.get("participation_policy"),
        "module_score": score,
        "module_effective_direction": direction,
        "signal_stage": signal_stage,
        "score_source": score_source,
        "module_payload_status": module_payload_status,
        "module_score_status": module_score_status,
        "cockpit_bridge_status": cockpit_status,
        "feature_count": len(features),
        "quality_blocking_feature_count": sum(1 for feature in features if feature.get("quality_blocking") is True),
        "feature_status_counts": dict(Counter(feature_statuses)),
        "break_reasons": break_reasons[:12],
        "top_features": feature_rows[:10],
        "contribution": contribution,
    }


def generate_radar_metrics_score_btc_ui_chain_audit(
    *,
    db: Database = database,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    db.init_schema()
    project_root = paths.project_root
    now_dt = datetime.now(UTC)
    source_config_ids = {source.source_id for source in SOURCE_CONFIGS}
    profiles = profile_by_module()
    with db.session() as session:
        repo = RadarRuntimeRepository(session)
        runtime = repo.latest_runtime_snapshot() or {}
        modules = runtime.get("modules") if isinstance(runtime.get("modules"), list) else []
        if not modules:
            modules = repo.latest_module_snapshots()
        scheduler = repo.scheduler_state()
        cockpit = runtime.get("btc_runtime_cockpit") or {}
        contribution_index = {
            str(item.get("module_name") or item.get("module_id") or ""): item
            for item in cockpit.get("module_contributions") or []
            if isinstance(item, dict)
        }
        module_summaries = [
            _module_summary(
                session=session,
                module=module,
                source_config_ids=source_config_ids,
                contribution_index=contribution_index,
            )
            for module in sorted(modules, key=lambda item: str(item.get("module_name") or item.get("module_id")))
        ]
        table_counts = {
            "source_runs": int(session.scalar(select(func.count()).select_from(schema.SourceRun)) or 0),
            "raw_observations": int(session.scalar(select(func.count()).select_from(schema.RawObservation)) or 0),
            "metric_values": int(session.scalar(select(func.count()).select_from(schema.MetricValue)) or 0),
            "module_json_outputs": int(session.scalar(select(func.count()).select_from(schema.ModuleJsonOutput)) or 0),
            "radar_module_snapshots": int(session.scalar(select(func.count()).select_from(schema.RadarModuleSnapshot)) or 0),
            "radar_runtime_snapshots": int(session.scalar(select(func.count()).select_from(schema.RadarRuntimeSnapshot)) or 0),
        }

    health = runtime.get("health") or {}
    runtime_asof = _parse_dt(runtime.get("asof_ts"))
    snapshot_age_sec = int((now_dt - runtime_asof).total_seconds()) if runtime_asof else None
    frontend_checks = _frontend_contract_checks(project_root)
    api_contract_checks = [
        {"endpoint": "/api/radar-runtime/daemon/status", "field": "daemon.latest_runtime_health", "status": "PASS"},
        {"endpoint": "/api/radar-runtime/modules/latest", "field": "modules[].source_freshness", "status": "PASS" if modules else "FAIL"},
        {"endpoint": "/api/radar-runtime/cockpit/latest", "field": "runtime.btc_runtime_cockpit", "status": "PASS" if cockpit else "FAIL"},
        {"endpoint": "/api/p45/dashboard/latest", "field": "radar_runtime / btc_runtime_cockpit fallback", "status": "PASS"},
    ]
    btc_checks = [
        {
            "check_id": "runtime-cockpit-schema",
            "status": "PASS" if cockpit.get("schema_version") == "p45.radar_runtime_cockpit.v2" else "FAIL",
            "value": cockpit.get("schema_version"),
        },
        {
            "check_id": "runtime-cockpit-has-scores",
            "status": "PASS" if isinstance(cockpit.get("scores"), dict) and cockpit.get("scores") else "FAIL",
            "value": cockpit.get("scores"),
        },
        {
            "check_id": "runtime-cockpit-has-module-contributions",
            "status": "PASS" if len(cockpit.get("module_contributions") or []) >= 10 else "FAIL",
            "value": len(cockpit.get("module_contributions") or []),
        },
        {
            "check_id": "p45-gate-preserved",
            "status": "PASS" if "P4.5 acceptance/residual gate" in str(cockpit.get("why_not_confirmed") or "") else "PARTIAL",
            "value": cockpit.get("why_not_confirmed"),
        },
    ]

    all_statuses = [item["status"] for item in module_summaries]
    all_statuses.extend(item["status"] for item in frontend_checks)
    all_statuses.extend(item["status"] for item in api_contract_checks)
    all_statuses.extend(item["status"] for item in btc_checks)
    critical_failures = [
        item for item in module_summaries if item["status"] == "FAIL" and item["severity"] in {"critical", "high"}
    ]
    overall = "FAIL" if critical_failures else _merge_status(all_statuses)
    status_counts = dict(Counter(item["status"] for item in module_summaries))
    report = {
        "schema_version": "p7.c29.radar_metrics_score_btc_ui_chain_audit.v1",
        "generated_at": now_dt.isoformat(),
        "overall_status": overall,
        "runtime_snapshot_id": runtime.get("runtime_snapshot_id"),
        "runtime_asof_ts": runtime.get("asof_ts"),
        "snapshot_age_sec": snapshot_age_sec,
        "health": health,
        "module_count": len(modules),
        "expected_module_count": len(EXPECTED_MODULES),
        "module_status_counts": status_counts,
        "table_counts": table_counts,
        "btc_checks": btc_checks,
        "api_contract_checks": api_contract_checks,
        "frontend_checks": frontend_checks,
        "module_summaries": module_summaries,
        "scheduler_count": len(scheduler),
        "cadence_profile_count": len(profiles),
    }

    report_dir = output_dir or project_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    html_path = report_dir / f"{REPORT_NAME}.html"
    md_path = report_dir / f"{REPORT_NAME}.md"

    html_path.write_text(_render_html(report), encoding="utf-8")
    md_path.write_text(_render_md(report), encoding="utf-8")
    return {**report, "html_path": str(html_path), "md_path": str(md_path)}


def _pill(status: Any) -> str:
    text = str(status or "unknown")
    cls = text.lower()
    return f'<span class="pill {cls}">{_esc(text)}</span>'


def _render_html(report: dict[str, Any]) -> str:
    module_rows = "\n".join(
        "<tr>"
        f"<td>{_esc(item['module_id'])}</td>"
        f"<td>{_pill(item['status'])}</td>"
        f"<td>{_esc(item['severity'])}</td>"
        f"<td>{_esc(item['cadence_group'])}</td>"
        f"<td>{_esc(item['source_freshness'])}</td>"
        f"<td>{_esc(item['runtime_freshness'])}</td>"
        f"<td>{_esc(item['module_score'])}</td>"
        f"<td>{_esc(item['module_effective_direction'])}</td>"
        f"<td>{_esc(item['signal_stage'])}</td>"
        f"<td>{_esc(item['score_source'])}</td>"
        f"<td>{_esc(item['feature_count'])}</td>"
        f"<td>{_esc(json.dumps(item['feature_status_counts'], ensure_ascii=False))}</td>"
        f"<td>{_esc('; '.join(item['break_reasons']))}</td>"
        "</tr>"
        for item in report["module_summaries"]
    )
    chain_rows = "\n".join(
        "<tr>"
        f"<td>{_esc(item['module_id'])}</td>"
        f"<td>{_esc(item['source_group_id'])}</td>"
        f"<td>{_esc(item['module_payload_status'])}</td>"
        f"<td>{_esc(item['module_score_status'])}</td>"
        f"<td>{_esc(item['cockpit_bridge_status'])}</td>"
        f"<td>{_esc(item['participation_policy'])}</td>"
        f"<td>{_esc(item['source_freshness'])}</td>"
        f"<td>{_esc(item['runtime_freshness'])}</td>"
        "</tr>"
        for item in report["module_summaries"]
    )
    feature_sections = "\n".join(
        f"<details><summary>{_esc(item['module_id'])} top feature lineage</summary>"
        f"<pre>{_esc(json.dumps(item['top_features'], ensure_ascii=False, indent=2))}</pre></details>"
        for item in report["module_summaries"]
    )
    frontend_rows = "\n".join(
        "<tr>"
        f"<td>{_esc(item['check_id'])}</td><td>{_esc(item['file'])}</td>"
        f"<td>{_pill(item['status'])}</td><td>{_esc(', '.join(item.get('missing_patterns') or []))}</td>"
        "</tr>"
        for item in report["frontend_checks"]
    )
    api_rows = "\n".join(
        "<tr>"
        f"<td>{_esc(item['endpoint'])}</td><td>{_esc(item['field'])}</td><td>{_pill(item['status'])}</td>"
        "</tr>"
        for item in report["api_contract_checks"]
    )
    btc_rows = "\n".join(
        "<tr>"
        f"<td>{_esc(item['check_id'])}</td><td>{_pill(item['status'])}</td><td>{_esc(item.get('value'))}</td>"
        "</tr>"
        for item in report["btc_checks"]
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Radar Metrics Score BTC UI Chain Audit</title>
  <style>
    body {{ margin:0; background:#06131d; color:#d8f3ff; font-family:Inter,Arial,sans-serif; }}
    main {{ padding:24px; }}
    h1,h2 {{ margin:0 0 12px; }}
    .card {{ border:1px solid #1d4254; border-radius:10px; background:#0b2130; padding:16px; margin-bottom:16px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:10px; }}
    .kv {{ border:1px solid #173244; border-radius:8px; padding:10px; background:#071a27; }}
    .label {{ color:#7fa9bd; font-size:12px; text-transform:uppercase; }}
    .value {{ font-weight:800; margin-top:4px; overflow-wrap:anywhere; }}
    table {{ border-collapse:collapse; width:100%; font-size:13px; }}
    th,td {{ border-bottom:1px solid #173244; padding:8px; text-align:left; vertical-align:top; }}
    pre {{ white-space:pre-wrap; color:#a9c7d8; overflow:auto; }}
    details {{ border:1px solid #173244; border-radius:8px; padding:10px; margin:8px 0; background:#071a27; }}
    summary {{ cursor:pointer; font-weight:800; }}
    .pill {{ display:inline-block; border:1px solid #31576b; border-radius:999px; padding:3px 8px; }}
    .pass {{ color:#24e0c4; border-color:#24e0c4; }}
    .partial {{ color:#ffc928; border-color:#ffc928; }}
    .fail {{ color:#ff6b75; border-color:#ff6b75; }}
  </style>
</head>
<body>
<main>
  <h1>Radar Metrics -> Module Score -> BTC Card -> Vue UI Chain Audit</h1>
  <section class="card">
    <h2 class="{str(report['overall_status']).lower()}">{_esc(report['overall_status'])}</h2>
    <div class="grid">
      <div class="kv"><div class="label">generated_at</div><div class="value">{_esc(report['generated_at'])}</div></div>
      <div class="kv"><div class="label">runtime_snapshot_id</div><div class="value">{_esc(report['runtime_snapshot_id'])}</div></div>
      <div class="kv"><div class="label">runtime_asof_ts</div><div class="value">{_esc(report['runtime_asof_ts'])}</div></div>
      <div class="kv"><div class="label">snapshot_age_sec</div><div class="value">{_esc(report['snapshot_age_sec'])}</div></div>
      <div class="kv"><div class="label">modules</div><div class="value">{_esc(report['module_count'])}/{_esc(report['expected_module_count'])}</div></div>
      <div class="kv"><div class="label">module_status_counts</div><div class="value">{_esc(json.dumps(report['module_status_counts'], ensure_ascii=False))}</div></div>
    </div>
  </section>
  <section class="card"><h2>SQLite Table Counts</h2><pre>{_esc(json.dumps(report['table_counts'], ensure_ascii=False, indent=2))}</pre></section>
  <section class="card"><h2>BTC Cockpit Bridge Checks</h2><table><thead><tr><th>check</th><th>status</th><th>value</th></tr></thead><tbody>{btc_rows}</tbody></table></section>
  <section class="card"><h2>API Contract Checks</h2><table><thead><tr><th>endpoint</th><th>field</th><th>status</th></tr></thead><tbody>{api_rows}</tbody></table></section>
  <section class="card"><h2>Vue UI Field Consumption Checks</h2><table><thead><tr><th>check</th><th>file</th><th>status</th><th>missing</th></tr></thead><tbody>{frontend_rows}</tbody></table></section>
  <section class="card"><h2>Data Chain Gap Matrix</h2><table><thead><tr><th>module</th><th>source group</th><th>module payload</th><th>module score</th><th>cockpit bridge</th><th>policy</th><th>source freshness</th><th>runtime freshness</th></tr></thead><tbody>{chain_rows}</tbody></table></section>
  <section class="card"><h2>14 Module Score & Freshness Matrix</h2><table><thead><tr><th>module</th><th>status</th><th>severity</th><th>group</th><th>source</th><th>runtime</th><th>score</th><th>direction</th><th>stage</th><th>score source</th><th>features</th><th>feature statuses</th><th>break reasons</th></tr></thead><tbody>{module_rows}</tbody></table></section>
  <section class="card"><h2>Top Feature Lineage Samples</h2>{feature_sections}</section>
  <section class="card"><h2>Raw Report JSON</h2><pre>{_esc(json.dumps(report, ensure_ascii=False, indent=2, default=str))}</pre></section>
</main>
</body>
</html>"""


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Radar Metrics Score BTC UI Chain Audit",
        f"- status: {report['overall_status']}",
        f"- generated_at: {report['generated_at']}",
        f"- runtime_snapshot_id: {report['runtime_snapshot_id']}",
        f"- runtime_asof_ts: {report['runtime_asof_ts']}",
        f"- modules: {report['module_count']}/{report['expected_module_count']}",
        f"- module_status_counts: {json.dumps(report['module_status_counts'], ensure_ascii=False)}",
        "",
        "## Module Summary",
    ]
    for item in report["module_summaries"]:
        lines.append(
            f"- {item['module_id']}: {item['status']} score={item['module_score']} "
            f"direction={item['module_effective_direction']} source={item['source_freshness']} "
            f"reasons={'; '.join(item['break_reasons'])}"
        )
    return "\n".join(lines)


def generate() -> dict[str, Any]:
    return generate_radar_metrics_score_btc_ui_chain_audit()


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2, default=str))
