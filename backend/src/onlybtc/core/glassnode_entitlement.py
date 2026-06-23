from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from onlybtc.core.config import Settings, get_settings
from onlybtc.core.paths import paths

GLASSNODE_ENTITLEMENT_SCHEMA_VERSION = "p10.c08.glassnode_entitlement.v1"
REPORT_JSON = paths.project_root / "reports" / "glassnode-provider-entitlement-report.json"
REPORT_MD = paths.project_root / "reports" / "glassnode-provider-entitlement-report.md"


@dataclass(frozen=True)
class GlassnodeMetricTarget:
    metric_id: str
    endpoint: str
    params: dict[str, str]
    expected_fields: tuple[str, ...] = ("t", "v")


GLASSNODE_TARGETS: tuple[GlassnodeMetricTarget, ...] = (
    GlassnodeMetricTarget(
        metric_id="realized_price",
        endpoint="/v1/metrics/market/price_realized_usd",
        params={"a": "BTC", "i": "24h"},
    ),
    GlassnodeMetricTarget(
        metric_id="sth_cost_basis",
        endpoint="/v1/metrics/indicators/realized_price_short_term_holders",
        params={"a": "BTC", "i": "24h"},
    ),
    GlassnodeMetricTarget(
        metric_id="lth_cost_basis",
        endpoint="/v1/metrics/indicators/realized_price_long_term_holders",
        params={"a": "BTC", "i": "24h"},
    ),
    GlassnodeMetricTarget(
        metric_id="whale_flow",
        endpoint="/v1/metrics/transactions/transfers_volume_to_exchanges_mean",
        params={"a": "BTC", "i": "24h"},
    ),
    GlassnodeMetricTarget(
        metric_id="miner_flow",
        endpoint="/v1/metrics/mining/miners_outflow_volume_sum",
        params={"a": "BTC", "i": "24h"},
    ),
    GlassnodeMetricTarget(
        metric_id="stablecoin_exchange_inflow",
        endpoint="/v1/metrics/transactions/stablecoin_transfers_volume_to_exchanges_sum",
        params={"a": "USDT", "i": "24h"},
    ),
    GlassnodeMetricTarget(
        metric_id="exchange_netflow",
        endpoint="/v1/metrics/transactions/transfers_volume_exchanges_net",
        params={"a": "BTC", "i": "24h"},
    ),
)


async def run_glassnode_entitlement_audit(
    *,
    settings: Settings | None = None,
    mode: str = "dry_run",
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"dry_run", "mock"}:
        raise ValueError("mode must be 'dry_run' or 'mock'")

    generated_at = datetime.now(UTC).isoformat()
    key = _clean_secret(settings.glassnode_api_key)
    targets = [_target_payload(target) for target in GLASSNODE_TARGETS]
    if normalized_mode == "mock":
        items = [_mock_item(target, index) for index, target in enumerate(GLASSNODE_TARGETS)]
    elif not key:
        items = [_missing_key_item(target) for target in GLASSNODE_TARGETS]
    else:
        items = await _audit_targets(
            GLASSNODE_TARGETS,
            api_key=key,
            timeout_seconds=timeout_seconds or settings.source_timeout_seconds,
        )

    available = [item for item in items if item["entitlement_status"] == "available"]
    locked = [item for item in items if item["entitlement_status"] != "available"]
    report = {
        "schema_version": GLASSNODE_ENTITLEMENT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "provider_id": "glassnode",
        "mode": normalized_mode,
        "applied_to_production": False,
        "configured": bool(key) or normalized_mode == "mock",
        "auth_methods": ["api_key", "manual_login_playwright"],
        "target_count": len(targets),
        "available_count": len(available),
        "locked_count": len(locked),
        "overall_status": "ready_for_candidate_review"
        if available
        else ("mock_only" if normalized_mode == "mock" else "provider_locked"),
        "targets": targets,
        "items": items,
        "production_write_candidates": [
            item["metric_id"] for item in available if item["production_write_allowed"] is True
        ],
        "guardrails": [
            "audit_only_no_metric_write",
            "do_not_fabricate_provider_locked_metrics",
            "do_not_persist_api_key_or_session_cookie",
            "unauthorized_rate_limited_schema_changed_are_non_fatal",
        ],
    }
    return _redact_report(report, key)


def write_glassnode_entitlement_report(report: dict[str, Any]) -> dict[str, Any]:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_glassnode_entitlement_markdown(report), encoding="utf-8")
    return {**report, "json_path": str(REPORT_JSON), "md_path": str(REPORT_MD)}


def latest_glassnode_entitlement_report(
    json_path: Path = REPORT_JSON,
) -> dict[str, Any] | None:
    if not json_path.exists():
        return None
    return json.loads(json_path.read_text(encoding="utf-8"))


def render_glassnode_entitlement_markdown(report: dict[str, Any]) -> str:
    candidates = [f"- `{item}`" for item in report["production_write_candidates"]] or ["- none"]
    lines = [
        "# Glassnode Provider Entitlement Report",
        "",
        f"- schema_version: `{report['schema_version']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- provider_id: `{report['provider_id']}`",
        f"- mode: `{report['mode']}`",
        f"- applied_to_production: `{report['applied_to_production']}`",
        f"- overall_status: `{report['overall_status']}`",
        f"- configured: `{report['configured']}`",
        f"- available_count: `{report['available_count']}`",
        f"- locked_count: `{report['locked_count']}`",
        "",
        "## Guardrails",
        "",
        *[f"- {item}" for item in report["guardrails"]],
        "",
        "## Entitlements",
        "",
        "| metric | status | http | quality | locked_reason | endpoint |",
        "|---|---|---:|---:|---|---|",
    ]
    for item in report["items"]:
        lines.append(
            "| {metric} | {status} | {http} | {quality} | {reason} | `{endpoint}` |".format(
                metric=item["metric_id"],
                status=item["entitlement_status"],
                http=item.get("http_status") or "",
                quality=item.get("quality") or "",
                reason=str(item.get("locked_reason") or "").replace("|", "/"),
                endpoint=item["endpoint"],
            )
        )
    lines.extend(
        [
            "",
            "## Production Write Candidates",
            "",
            *candidates,
            "",
            "## Notes",
            "",
            "- This report is audit-only and does not write metrics.",
            "- Available metrics still require source lineage, freshness, and quality "
            "review before production use.",
        ]
    )
    return "\n".join(lines) + "\n"


async def _audit_targets(
    targets: tuple[GlassnodeMetricTarget, ...],
    *,
    api_key: str,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(
        base_url="https://api.glassnode.com",
        timeout=timeout_seconds,
    ) as client:
        items = []
        for target in targets:
            items.append(await _audit_target(client, target, api_key=api_key))
        return items


async def _audit_target(
    client: httpx.AsyncClient,
    target: GlassnodeMetricTarget,
    *,
    api_key: str,
) -> dict[str, Any]:
    params = {**target.params, "api_key": api_key}
    try:
        response = await client.get(target.endpoint, params=params)
    except httpx.HTTPError as exc:
        return _locked_item(
            target,
            status="provider_error",
            locked_reason=_redact_text(str(exc), api_key),
        )

    if response.status_code == 200:
        return _available_or_schema_changed(target, response)
    if response.status_code in {401, 403}:
        return _locked_item(
            target,
            status="unauthorized",
            http_status=response.status_code,
            locked_reason="api_key_not_entitled_or_invalid",
        )
    if response.status_code == 429:
        return _locked_item(
            target,
            status="rate_limited",
            http_status=response.status_code,
            locked_reason="provider_rate_limited",
        )
    if response.status_code == 404:
        return _locked_item(
            target,
            status="not_found",
            http_status=response.status_code,
            locked_reason="endpoint_not_found_or_metric_unavailable",
        )
    return _locked_item(
        target,
        status="provider_error",
        http_status=response.status_code,
        locked_reason=f"unexpected_http_status_{response.status_code}",
    )


def _available_or_schema_changed(
    target: GlassnodeMetricTarget,
    response: httpx.Response,
) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return _locked_item(
            target,
            status="schema_changed",
            http_status=response.status_code,
            locked_reason="non_json_payload",
        )
    latest = payload[-1] if isinstance(payload, list) and payload else None
    if not isinstance(latest, dict) or any(field not in latest for field in target.expected_fields):
        return _locked_item(
            target,
            status="schema_changed",
            http_status=response.status_code,
            locked_reason="expected_t_v_fields_missing",
        )
    return {
        **_base_item(target),
        "entitlement_status": "available",
        "http_status": response.status_code,
        "business_ts": _business_ts(latest.get("t")),
        "quality": 0.85,
        "locked_reason": "",
        "production_write_allowed": True,
        "sample_keys": sorted(str(key) for key in latest.keys()),
    }


def _target_payload(target: GlassnodeMetricTarget) -> dict[str, Any]:
    return {
        "metric_id": target.metric_id,
        "endpoint": target.endpoint,
        "params": dict(target.params),
        "expected_fields": list(target.expected_fields),
    }


def _mock_item(target: GlassnodeMetricTarget, index: int) -> dict[str, Any]:
    if index == 0:
        return {
            **_base_item(target),
            "entitlement_status": "available",
            "http_status": 200,
            "business_ts": "2026-06-23T00:00:00+00:00",
            "quality": 0.85,
            "locked_reason": "",
            "production_write_allowed": True,
            "sample_keys": ["t", "v"],
        }
    return _locked_item(
        target,
        status="unauthorized",
        http_status=403,
        locked_reason="mock_provider_locked",
    )


def _missing_key_item(target: GlassnodeMetricTarget) -> dict[str, Any]:
    return _locked_item(
        target,
        status="missing_key",
        locked_reason="ONLYBTC_GLASSNODE_API_KEY is not configured.",
    )


def _locked_item(
    target: GlassnodeMetricTarget,
    *,
    status: str,
    locked_reason: str,
    http_status: int | None = None,
) -> dict[str, Any]:
    return {
        **_base_item(target),
        "entitlement_status": status,
        "http_status": http_status,
        "business_ts": None,
        "quality": None,
        "locked_reason": locked_reason,
        "production_write_allowed": False,
        "sample_keys": [],
    }


def _base_item(target: GlassnodeMetricTarget) -> dict[str, Any]:
    return {
        "provider_id": "glassnode",
        "auth_method": "api_key",
        "metric_id": target.metric_id,
        "endpoint": target.endpoint,
        "source_id": f"glassnode-api-{target.metric_id.replace('_', '-')}",
    }


def _business_ts(value: Any) -> str | None:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(float(value), tz=UTC).isoformat()
    if isinstance(value, str):
        return value
    return None


def _clean_secret(value: str | None) -> str:
    value = (value or "").strip()
    if not value or value.lower().startswith("your_"):
        return ""
    return value


def _redact_report(report: dict[str, Any], secret: str) -> dict[str, Any]:
    text = json.dumps(report, ensure_ascii=False)
    text = _redact_text(text, secret)
    return json.loads(text)


def _redact_text(text: str, secret: str) -> str:
    redacted = text
    if secret:
        redacted = redacted.replace(secret, "<redacted>")
    redacted = re.sub(r"api_key=([^&\\s]+)", "api_key=<redacted>", redacted)
    redacted = re.sub(r"Bearer\\s+[^\\s]+", "Bearer <redacted>", redacted)
    return redacted
