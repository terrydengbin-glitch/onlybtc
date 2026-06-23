from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as XET

import httpx

from onlybtc.core.paths import paths
from onlybtc.event_window.connectors.common import ET, FetchResult, clean_text, stable_hash

HEADERS = {
    "User-Agent": "onlyBTC EventWatchtower/1.0 (+https://localhost)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
JSON_HEADERS = {
    "User-Agent": "onlyBTC EventWatchtower/1.0 (+https://localhost)",
    "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
}
FAIRECONOMY_CACHE_PATH = paths.cache_dir / "event_window" / "faireconomy_ff_calendar_thisweek.json"
FAIRECONOMY_XML_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
SECONDARY_GUARD_PATH = paths.cache_dir / "event_window" / "secondary_source_guard.json"
SECONDARY_CACHE_DIR = paths.cache_dir / "event_window" / "secondary_provider_cache"

DEFAULT_GUARD = {
    "min_interval_sec": 1800,
    "cache_ttl_sec": 3600,
    "error_backoff_sec": {"429": 7200, "403": 21600, "timeout": 1800, "default": 1800},
    "use_stale_cache_when_blocked": True,
}

PROVIDER_GUARDS: dict[str, dict[str, Any]] = {
    "faireconomy-ff-calendar-thisweek-json": {
        "min_interval_sec": 1800,
        "cache_ttl_sec": 3600,
        "error_backoff_sec": {"429": 7200, "403": 21600, "timeout": 1800, "default": 1800},
        "use_stale_cache_when_blocked": True,
    },
    "fxstreet-calendar": {
        "min_interval_sec": 1800,
        "cache_ttl_sec": 3600,
        "error_backoff_sec": {"403": 21600, "timeout": 1800, "default": 1800},
        "use_stale_cache_when_blocked": True,
    },
    "dukascopy-economic-calendar-free": {
        "min_interval_sec": 3600,
        "cache_ttl_sec": 7200,
        "error_backoff_sec": {"403": 21600, "timeout": 3600, "default": 3600},
        "use_stale_cache_when_blocked": True,
    },
    "fxcm-economic-calendar-free": {
        "min_interval_sec": 21600,
        "cache_ttl_sec": 86400,
        "error_backoff_sec": {"403": 86400, "timeout": 21600, "default": 21600},
        "use_stale_cache_when_blocked": True,
    },
}

SECONDARY_PROVIDERS = [
    {
        "source_id": "faireconomy-ff-calendar-thisweek-json",
        "source_tier": "secondary_calendar_free_export",
        "url": "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        "confidence": 0.80,
        "kind": "faireconomy_json",
        "replacement_for": "forex-factory-calendar",
        "provides": ["schedule", "impact", "forecast", "previous"],
        "missing": ["actual"],
    },
    {
        "source_id": "fxstreet-calendar",
        "source_tier": "secondary_consensus_actual_free_crosscheck",
        "url": "https://www.fxstreet.com/economic-calendar",
        "confidence": 0.82,
        "kind": "html_crosscheck",
        "action": "keep_and_improve_parser",
    },
    {
        "source_id": "tradays-calendar-free",
        "source_tier": "secondary_consensus_actual_free",
        "url": "https://www.tradays.com/en",
        "confidence": 0.72,
        "kind": "provider_stub",
        "replacement_for": "myfxbook-calendar,investing-calendar",
        "disabled_reason": "no_stable_backend_endpoint_without_mt5_bridge",
    },
    {
        "source_id": "myfxbook-calendar",
        "source_tier": "secondary_consensus",
        "url": "https://www.myfxbook.com/forex-economic-calendar",
        "confidence": 0.78,
        "kind": "disabled",
        "replacement": "tradays-calendar-free",
        "disabled_reason": "403_or_cloudflare_challenge",
    },
    {
        "source_id": "forex-factory-calendar",
        "source_tier": "secondary_calendar",
        "url": "https://www.forexfactory.com/calendar",
        "confidence": 0.80,
        "kind": "disabled",
        "replacement": "faireconomy-ff-calendar-thisweek-json",
        "disabled_reason": "cloudflare_html_unstable",
    },
    {
        "source_id": "investing-calendar",
        "source_tier": "secondary_consensus",
        "url": "https://www.investing.com/economic-calendar/",
        "confidence": 0.83,
        "kind": "disabled",
        "replacement": "tradays-calendar-free",
        "disabled_reason": "403_or_html_scrape_unstable",
    },
    {
        "source_id": "dukascopy-economic-calendar-free",
        "source_tier": "secondary_consensus_actual_free_crosscheck",
        "url": "https://www.dukascopy.com/swiss/english/fx-market-tools/economic-calendar/",
        "confidence": 0.74,
        "kind": "html_crosscheck",
        "optional": True,
    },
    {
        "source_id": "fxcm-economic-calendar-free",
        "source_tier": "secondary_consensus_free_crosscheck",
        "url": "https://www.fxcm.com/markets/research/economic-calendar/",
        "confidence": 0.70,
        "kind": "html_crosscheck",
        "optional": True,
    },
]

EVENT_KEYWORDS = {
    "CPI": ["consumer price index", "cpi", "core cpi"],
    "PPI": ["producer price index", "ppi"],
    "NFP": ["nonfarm payroll", "employment situation", "unemployment rate"],
    "PCE": ["personal income and outlays", "pce", "core pce"],
    "FOMC": ["fomc", "fed interest rate", "federal reserve"],
    "JOLTS": ["jolts", "job openings"],
    "ECI": ["employment cost index"],
    "GDP": ["gross domestic product", "gdp"],
}


def collect_secondary_calendar_mesh(event: dict[str, Any], now: datetime) -> dict[str, Any]:
    asof = now if now.tzinfo else now.replace(tzinfo=UTC)
    event_type = str(event.get("event_type") or "").upper()
    fetches: list[dict[str, Any]] = []
    providers: list[dict[str, Any]] = []
    consensus_candidates: list[dict[str, Any]] = []
    actual_candidates: list[dict[str, Any]] = []
    calendar_hits: list[dict[str, Any]] = []

    for provider in SECONDARY_PROVIDERS:
        kind = str(provider.get("kind") or "html_crosscheck")
        if kind == "disabled":
            fetch_payload = _disabled_fetch(provider, asof)
            fetches.append(fetch_payload)
            providers.append(_provider_payload(provider, fetch_payload, [], {}, status="disabled"))
            continue
        if kind == "provider_stub":
            fetch_payload = _stub_fetch(provider, asof)
            fetches.append(fetch_payload)
            providers.append(_provider_payload(provider, fetch_payload, [], {}, status="provider_stub"))
            continue

        hits: list[dict[str, Any]] = []
        parsed_values: dict[str, float | None] = {}
        if kind == "faireconomy_json":
            guard = _guard_decision(provider, asof)
            if not guard["allowed"]:
                cached_text = _read_cache(guard["cache_path"])
                if cached_text:
                    hits, parsed_values, parsed_count = _parse_faireconomy_json(cached_text, event_type, asof)
                    fetch_payload = _guarded_fetch_payload(
                        provider,
                        asof,
                        status=guard["status"],
                        error_code=guard["error_code"],
                        error_message=guard["message"],
                        payload_hash=stable_hash(cached_text),
                        parsed_item_count=parsed_count,
                        fallback_used=True,
                        guard=guard,
                        cache_status="served_cached",
                    )
                else:
                    fetch_payload = _guarded_fetch_payload(
                        provider,
                        asof,
                        status=guard["status"],
                        error_code=guard["error_code"],
                        error_message=guard["message"],
                        parsed_item_count=0,
                        fallback_used=False,
                        guard=guard,
                        cache_status="cache_missing",
                    )
                fetches.append(fetch_payload)
                provider_payload = _provider_payload(provider, fetch_payload, hits, parsed_values)
                providers.append(provider_payload)
                calendar_hits.extend(
                    {
                        "provider": provider["source_id"],
                        "source_tier": provider["source_tier"],
                        **hit,
                    }
                    for hit in hits
                )
                if parsed_values.get("consensus") is not None:
                    consensus_candidates.append(
                        {
                            "provider": provider["source_id"],
                            "value": parsed_values["consensus"],
                            "confidence": provider["confidence"],
                        }
                    )
                continue
            response, started, finished, error = _get(provider["url"], headers=JSON_HEADERS)
            if response is not None and response.status_code < 400:
                hits, parsed_values, parsed_count = _parse_faireconomy_json(response.text, event_type, asof)
                _write_cache(FAIRECONOMY_CACHE_PATH, response.text)
                _write_cache(guard["cache_path"], response.text)
                fetch = FetchResult(
                    source_id=provider["source_id"],
                    source_tier=provider["source_tier"],
                    endpoint_url=provider["url"],
                    started_at=started,
                    finished_at=finished,
                    status="success" if hits else "partial",
                    http_status=response.status_code,
                    payload_hash=stable_hash(response.text),
                    parsed_item_count=parsed_count,
                )
                _record_guard(provider, finished, http_status=response.status_code, status="success")
            elif response is not None and response.status_code == 429:
                _record_guard(provider, finished, http_status=response.status_code, status="backoff")
                cached_text = _read_cache(guard["cache_path"]) or _read_cache(FAIRECONOMY_CACHE_PATH)
                if cached_text:
                    hits, parsed_values, parsed_count = _parse_faireconomy_json(cached_text, event_type, asof)
                    fetch = FetchResult(
                        source_id=provider["source_id"],
                        source_tier=provider["source_tier"],
                        endpoint_url=provider["url"],
                        started_at=started,
                        finished_at=finished,
                        status="partial",
                        http_status=response.status_code,
                        error_code="rate_limited_cache_used",
                        error_message="faireconomy rate limited; using cached weekly export",
                        payload_hash=stable_hash(cached_text),
                        parsed_item_count=parsed_count,
                        fallback_used=True,
                    )
                else:
                    fetch = FetchResult(
                        source_id=provider["source_id"],
                        source_tier=provider["source_tier"],
                        endpoint_url=provider["url"],
                        started_at=started,
                        finished_at=finished,
                        status="backoff",
                        http_status=response.status_code,
                        error_code="rate_limited_no_cache",
                        error_message="faireconomy rate limited and no cache available",
                        parsed_item_count=0,
                    )
            else:
                _record_guard(
                    provider,
                    finished,
                    http_status=response.status_code if response is not None else None,
                    status="backoff",
                    error_key="timeout" if response is None else None,
                )
                fetch = FetchResult(
                    source_id=provider["source_id"],
                    source_tier=provider["source_tier"],
                    endpoint_url=provider["url"],
                    started_at=started,
                    finished_at=finished,
                    status="failed",
                    http_status=response.status_code if response is not None else None,
                    error_code="http_error" if response is not None else "network_error",
                    error_message=error
                    or (response.text[:240] if response is not None else "request failed"),
                )
        else:
            guard = _guard_decision(provider, asof)
            if not guard["allowed"]:
                cached_text = _read_cache(guard["cache_path"])
                if cached_text:
                    text = _visible_text(cached_text)
                    hits = _extract_hits(text, event_type)
                    parsed_values = _extract_numeric_fields(text, event_type)
                    fetch_payload = _guarded_fetch_payload(
                        provider,
                        asof,
                        status=guard["status"],
                        error_code=guard["error_code"],
                        error_message=guard["message"],
                        payload_hash=stable_hash(cached_text),
                        parsed_item_count=len(hits),
                        fallback_used=True,
                        guard=guard,
                        cache_status="served_cached",
                    )
                else:
                    fetch_payload = _guarded_fetch_payload(
                        provider,
                        asof,
                        status=guard["status"],
                        error_code=guard["error_code"],
                        error_message=guard["message"],
                        parsed_item_count=0,
                        fallback_used=False,
                        guard=guard,
                        cache_status="cache_missing",
                    )
                fetches.append(fetch_payload)
                provider_payload = _provider_payload(provider, fetch_payload, hits, parsed_values)
                providers.append(provider_payload)
                calendar_hits.extend(
                    {
                        "provider": provider["source_id"],
                        "source_tier": provider["source_tier"],
                        **hit,
                    }
                    for hit in hits
                )
                if parsed_values.get("consensus") is not None:
                    consensus_candidates.append(
                        {
                            "provider": provider["source_id"],
                            "value": parsed_values["consensus"],
                            "confidence": provider["confidence"],
                        }
                    )
                if parsed_values.get("actual") is not None:
                    actual_candidates.append(
                        {
                            "provider": provider["source_id"],
                            "value": parsed_values["actual"],
                            "confidence": provider["confidence"],
                        }
                    )
                continue
            response, started, finished, error = _get(provider["url"])
            if response is not None and response.status_code < 400:
                text = _visible_text(response.text)
                hits = _extract_hits(text, event_type)
                parsed_values = _extract_numeric_fields(text, event_type)
                _write_cache(guard["cache_path"], response.text)
                fetch = FetchResult(
                    source_id=provider["source_id"],
                    source_tier=provider["source_tier"],
                    endpoint_url=provider["url"],
                    started_at=started,
                    finished_at=finished,
                    status="success" if hits else "partial",
                    http_status=response.status_code,
                    payload_hash=stable_hash(response.text),
                    parsed_item_count=len(hits),
                )
                _record_guard(provider, finished, http_status=response.status_code, status="success")
            else:
                _record_guard(
                    provider,
                    finished,
                    http_status=response.status_code if response is not None else None,
                    status="backoff",
                    error_key="timeout" if response is None else None,
                )
                status = "partial" if provider.get("optional") else "failed"
                if response is not None and response.status_code in {403, 429}:
                    status = "backoff"
                error_code = (
                    "optional_crosscheck_unavailable"
                    if provider.get("optional")
                    else ("http_error" if response is not None else "network_error")
                )
                fetch = FetchResult(
                    source_id=provider["source_id"],
                    source_tier=provider["source_tier"],
                    endpoint_url=provider["url"],
                    started_at=started,
                    finished_at=finished,
                    status=status,
                    http_status=response.status_code if response is not None else None,
                    error_code=error_code,
                    error_message=error
                    or (response.text[:240] if response is not None else "request failed"),
                )
        fetch_payload = _augment_fetch_payload(fetch.payload(), provider)
        fetches.append(fetch_payload)
        provider_payload = _provider_payload(provider, fetch_payload, hits, parsed_values)
        providers.append(provider_payload)
        calendar_hits.extend(
            {
                "provider": provider["source_id"],
                "source_tier": provider["source_tier"],
                **hit,
            }
            for hit in hits
        )
        if parsed_values.get("consensus") is not None:
            consensus_candidates.append(
                {
                    "provider": provider["source_id"],
                    "value": parsed_values["consensus"],
                    "confidence": provider["confidence"],
                }
            )
        if parsed_values.get("actual") is not None:
            actual_candidates.append(
                {
                    "provider": provider["source_id"],
                    "value": parsed_values["actual"],
                    "confidence": provider["confidence"],
                }
            )

    consensus = _confirmed_value(consensus_candidates)
    consensus_status = "secondary_confirmed" if consensus is not None else "missing"
    if consensus is None and consensus_candidates:
        consensus_status = "secondary_unconfirmed"
    secondary_calendar_status = "available" if calendar_hits else "missing"
    if not calendar_hits and any(item["status"] == "success" for item in providers):
        secondary_calendar_status = "unmatched"
    actual_fast = _confirmed_value(actual_candidates)
    actual_fast_status = "confirmed" if actual_fast is not None else "missing"
    if actual_fast is None and actual_candidates:
        actual_fast_status = "actual_fast_unconfirmed"
    return {
        "snapshot": {
            "asof_ts": asof.isoformat(),
            "event_id": event.get("event_id"),
            "event_type": event_type,
            "secondary_calendar_status": secondary_calendar_status,
            "consensus": consensus,
            "consensus_status": consensus_status,
            "consensus_sources": [
                item["provider"] for item in consensus_candidates
            ],
            "actual_fast": actual_fast,
            "actual_fast_sources": [item["provider"] for item in actual_candidates],
            "calendar_hits": calendar_hits[:8],
            "providers": providers,
            "disabled_providers": [
                item["provider"] for item in providers if item.get("status") == "disabled"
            ],
            "replacement_map": {
                item["provider"]: item.get("replacement")
                for item in providers
                if item.get("replacement")
            },
            "source_lineage": [
                item for item in fetches if item.get("status") in {"success", "partial"}
            ],
            "warning": "non_official_sources_used_for_watch_only",
            "actual_fast_status": actual_fast_status,
        },
        "source_fetches": fetches,
    }


def _get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[httpx.Response | None, datetime, datetime, str | None]:
    started = datetime.now(UTC)
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True, headers=headers or HEADERS) as client:
            response = client.get(url)
        return response, started, datetime.now(UTC), None
    except httpx.HTTPError as exc:
        return None, started, datetime.now(UTC), str(exc)


def _guard_config(source_id: str) -> dict[str, Any]:
    config = dict(DEFAULT_GUARD)
    override = PROVIDER_GUARDS.get(source_id) or {}
    config.update({key: value for key, value in override.items() if key != "error_backoff_sec"})
    error_backoff = dict(DEFAULT_GUARD["error_backoff_sec"])
    error_backoff.update(override.get("error_backoff_sec") or {})
    config["error_backoff_sec"] = error_backoff
    return config


def _guard_cache_path(provider: dict[str, Any]) -> Path:
    source_id = str(provider["source_id"])
    suffix = "json" if provider.get("kind") == "faireconomy_json" else "html"
    return SECONDARY_CACHE_DIR / f"{source_id}.{suffix}"


def _load_guard_state() -> dict[str, Any]:
    try:
        if SECONDARY_GUARD_PATH.exists():
            raw = json.loads(SECONDARY_GUARD_PATH.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        return {}
    return {}


def _save_guard_state(state: dict[str, Any]) -> None:
    try:
        SECONDARY_GUARD_PATH.parent.mkdir(parents=True, exist_ok=True)
        SECONDARY_GUARD_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        return


def _parse_guard_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _guard_decision(provider: dict[str, Any], asof: datetime) -> dict[str, Any]:
    source_id = str(provider["source_id"])
    config = _guard_config(source_id)
    state = _load_guard_state().get(source_id) or {}
    cache_path = _guard_cache_path(provider)
    next_allowed = _parse_guard_dt(state.get("next_allowed_at"))
    last_success = _parse_guard_dt(state.get("last_success_at"))
    cache_status = "cache_missing"
    if cache_path.exists():
        cache_status = "stale_cache"
        if last_success and (asof - last_success).total_seconds() <= int(config["cache_ttl_sec"]):
            cache_status = "fresh_cache"
    if next_allowed and next_allowed > asof:
        status = "backoff" if state.get("throttle_status") == "backoff_active" else "throttled"
        return {
            "allowed": False,
            "status": status,
            "error_code": "backoff_active" if status == "backoff" else "skipped_until_next_allowed",
            "message": f"secondary source guarded until {next_allowed.isoformat()}",
            "throttle_status": "backoff_active" if status == "backoff" else "skipped_until_next_allowed",
            "cache_status": cache_status,
            "next_allowed_at": next_allowed.isoformat(),
            "last_attempt_at": state.get("last_attempt_at"),
            "last_success_at": state.get("last_success_at"),
            "last_http_status": state.get("last_http_status"),
            "blocked_reason": state.get("blocked_reason"),
            "cache_path": cache_path,
        }
    return {
        "allowed": True,
        "status": "allowed",
        "error_code": "",
        "message": "",
        "throttle_status": "allowed",
        "cache_status": cache_status,
        "next_allowed_at": None,
        "last_attempt_at": state.get("last_attempt_at"),
        "last_success_at": state.get("last_success_at"),
        "last_http_status": state.get("last_http_status"),
        "blocked_reason": state.get("blocked_reason"),
        "cache_path": cache_path,
    }


def _record_guard(
    provider: dict[str, Any],
    finished_at: datetime,
    *,
    http_status: int | None,
    status: str,
    error_key: str | None = None,
) -> None:
    source_id = str(provider["source_id"])
    config = _guard_config(source_id)
    state = _load_guard_state()
    if status == "success":
        next_allowed = finished_at + timedelta(seconds=int(config["min_interval_sec"]))
        blocked_reason = None
        throttle_status = "allowed"
        last_success_at = finished_at.isoformat()
    else:
        key = error_key or str(http_status or "default")
        backoff = int((config.get("error_backoff_sec") or {}).get(key) or (config.get("error_backoff_sec") or {}).get("default") or 1800)
        next_allowed = finished_at + timedelta(seconds=backoff)
        blocked_reason = (
            "rate_limited_429"
            if http_status == 429
            else ("access_denied_403" if http_status == 403 else "provider_error_backoff")
        )
        throttle_status = "backoff_active"
        last_success_at = (state.get(source_id) or {}).get("last_success_at")
    state[source_id] = {
        **(state.get(source_id) or {}),
        "source_id": source_id,
        "last_attempt_at": finished_at.isoformat(),
        "last_success_at": last_success_at,
        "next_allowed_at": next_allowed.isoformat(),
        "last_http_status": http_status,
        "throttle_status": throttle_status,
        "blocked_reason": blocked_reason,
    }
    _save_guard_state(state)


def _augment_fetch_payload(payload: dict[str, Any], provider: dict[str, Any]) -> dict[str, Any]:
    source_id = str(provider["source_id"])
    state = _load_guard_state().get(source_id) or {}
    config = _guard_config(source_id)
    cache_path = _guard_cache_path(provider)
    cache_status = "cache_missing"
    last_success = _parse_guard_dt(state.get("last_success_at"))
    finished = _parse_guard_dt(payload.get("finished_at")) or datetime.now(UTC)
    if cache_path.exists():
        cache_status = "stale_cache"
        if last_success and (finished - last_success).total_seconds() <= int(config["cache_ttl_sec"]):
            cache_status = "fresh_cache"
    payload.setdefault("throttle_status", state.get("throttle_status") or "allowed")
    payload.setdefault("cache_status", cache_status)
    payload.setdefault("next_allowed_at", state.get("next_allowed_at"))
    payload.setdefault("last_http_status", payload.get("http_status") or state.get("last_http_status"))
    payload.setdefault("blocked_reason", state.get("blocked_reason"))
    payload.setdefault("min_interval_sec", config.get("min_interval_sec"))
    payload.setdefault("cache_ttl_sec", config.get("cache_ttl_sec"))
    return payload


def _guarded_fetch_payload(
    provider: dict[str, Any],
    asof: datetime,
    *,
    status: str,
    error_code: str,
    error_message: str,
    parsed_item_count: int,
    fallback_used: bool,
    guard: dict[str, Any],
    cache_status: str,
    payload_hash: str | None = None,
) -> dict[str, Any]:
    payload = FetchResult(
        source_id=provider["source_id"],
        source_tier=provider["source_tier"],
        endpoint_url=provider["url"],
        started_at=asof,
        finished_at=asof,
        status=status,
        http_status=guard.get("last_http_status"),
        error_code=error_code,
        error_message=error_message,
        payload_hash=payload_hash,
        parsed_item_count=parsed_item_count,
        fallback_used=fallback_used,
    ).payload()
    payload.update(
        {
            "throttle_status": guard.get("throttle_status"),
            "cache_status": cache_status,
            "next_allowed_at": guard.get("next_allowed_at"),
            "last_http_status": guard.get("last_http_status"),
            "blocked_reason": guard.get("blocked_reason"),
            "min_interval_sec": _guard_config(str(provider["source_id"])).get("min_interval_sec"),
            "cache_ttl_sec": _guard_config(str(provider["source_id"])).get("cache_ttl_sec"),
        }
    )
    return payload


def _visible_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return clean_text(unescape(text)).lower()


def _extract_hits(text: str, event_type: str) -> list[dict[str, Any]]:
    keywords = EVENT_KEYWORDS.get(event_type, [event_type.lower()])
    hits: list[dict[str, Any]] = []
    for keyword in keywords:
        index = text.find(keyword)
        if index < 0:
            continue
        start = max(0, index - 120)
        end = min(len(text), index + 180)
        hits.append(
            {
                "keyword": keyword,
                "snippet": clean_text(text[start:end])[:260],
            }
        )
    return hits[:4]


def _extract_numeric_fields(text: str, event_type: str) -> dict[str, float | None]:
    window = _event_window_text(text, event_type)
    return {
        "actual": _extract_labeled_number(window, ["actual"]),
        "consensus": _extract_labeled_number(window, ["consensus", "forecast"]),
        "previous": _extract_labeled_number(window, ["previous"]),
    }


def _event_window_text(text: str, event_type: str) -> str:
    keywords = EVENT_KEYWORDS.get(event_type, [event_type.lower()])
    indexes = [text.find(keyword) for keyword in keywords if text.find(keyword) >= 0]
    if not indexes:
        return ""
    index = min(indexes)
    return text[max(0, index - 800): min(len(text), index + 1600)]


def _extract_labeled_number(text: str, labels: list[str]) -> float | None:
    for label in labels:
        pattern = rf"{label}\s*[:：]?\s*(-?\d+(?:\.\d+)?)\s*%?"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            return float(match.group(1))
        except ValueError:
            continue
    return None


def _provider_payload(
    provider: dict[str, Any],
    fetch_payload: dict[str, Any],
    hits: list[dict[str, Any]],
    parsed_values: dict[str, float | None],
    *,
    status: str | None = None,
) -> dict[str, Any]:
    return {
        "provider": provider["source_id"],
        "source_tier": provider["source_tier"],
        "status": status or fetch_payload["status"],
        "confidence": provider["confidence"],
        "calendar_hit_count": len(hits),
        "has_event_reference": bool(hits),
        "values": parsed_values,
        "replacement_for": provider.get("replacement_for"),
        "replacement": provider.get("replacement"),
        "disabled_reason": provider.get("disabled_reason"),
        "fallback_used": bool(fetch_payload.get("fallback_used") or provider.get("replacement_for")),
        "throttle_status": fetch_payload.get("throttle_status"),
        "cache_status": fetch_payload.get("cache_status"),
        "next_allowed_at": fetch_payload.get("next_allowed_at"),
        "last_http_status": fetch_payload.get("last_http_status") or fetch_payload.get("http_status"),
        "blocked_reason": fetch_payload.get("blocked_reason"),
        "provides": provider.get("provides"),
        "missing": provider.get("missing"),
        "warning": (
            "provider_stub_no_fake_actual"
            if status == "provider_stub"
            else "secondary_source_not_official"
        ),
    }


def _disabled_fetch(provider: dict[str, Any], asof: datetime) -> dict[str, Any]:
    return FetchResult(
        source_id=provider["source_id"],
        source_tier=provider["source_tier"],
        endpoint_url=provider["url"],
        started_at=asof,
        finished_at=asof,
        status="disabled",
        error_code="provider_disabled",
        error_message=(
            f"{provider.get('disabled_reason')}; "
            f"replacement={provider.get('replacement')}"
        ),
    ).payload()


def _stub_fetch(provider: dict[str, Any], asof: datetime) -> dict[str, Any]:
    return FetchResult(
        source_id=provider["source_id"],
        source_tier=provider["source_tier"],
        endpoint_url=provider["url"],
        started_at=asof,
        finished_at=asof,
        status="provider_stub",
        error_code="provider_stub",
        error_message=provider.get("disabled_reason"),
    ).payload()


def _parse_faireconomy_json(
    text: str,
    event_type: str,
    asof: datetime,
) -> tuple[list[dict[str, Any]], dict[str, float | None], int]:
    try:
        items = json.loads(text)
    except ValueError:
        return [], {}, 0
    if not isinstance(items, list):
        return [], {}, 0
    keywords = EVENT_KEYWORDS.get(event_type, [event_type.lower()])
    hits: list[dict[str, Any]] = []
    consensus_candidates: list[float] = []
    previous_candidates: list[float] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        country = str(raw.get("country") or "").upper()
        if country not in {"USD", "US", "UNITED STATES"}:
            continue
        title = clean_text(str(raw.get("title") or ""))
        title_lower = title.lower()
        if not any(keyword in title_lower for keyword in keywords):
            continue
        event_dt = _parse_offset_datetime(str(raw.get("date") or ""))
        forecast = _parse_value(raw.get("forecast"))
        previous = _parse_value(raw.get("previous"))
        if forecast is not None:
            consensus_candidates.append(forecast)
        if previous is not None:
            previous_candidates.append(previous)
        hits.append(
            {
                "keyword": event_type.lower(),
                "title": title,
                "currency": country,
                "importance": raw.get("impact"),
                "event_time": event_dt.isoformat() if event_dt else None,
                "event_time_utc": event_dt.astimezone(UTC).isoformat() if event_dt else None,
                "event_time_et": event_dt.astimezone(ET).isoformat() if event_dt else None,
                "forecast_raw": raw.get("forecast"),
                "previous_raw": raw.get("previous"),
                "snippet": f"{title}; impact={raw.get('impact')}; forecast={raw.get('forecast')}; previous={raw.get('previous')}",
            }
        )
    parsed_values: dict[str, float | None] = {
        "actual": None,
        "consensus": consensus_candidates[0] if consensus_candidates else None,
        "previous": previous_candidates[0] if previous_candidates else None,
    }
    active_hits = [
        item for item in hits
        if _is_near_asof(item.get("event_time_utc"), asof)
    ]
    return (active_hits or hits)[:6], parsed_values, len(hits)


def _parse_faireconomy_xml(
    text: str,
    event_type: str,
    asof: datetime,
) -> tuple[list[dict[str, Any]], dict[str, float | None], int]:
    try:
        root = XET.fromstring(text)
    except XET.ParseError:
        return [], {}, 0
    items = []
    for event in root.findall(".//event"):
        items.append(
            {
                "title": _xml_text(event, "title"),
                "country": _xml_text(event, "country"),
                "date": _xml_datetime(event),
                "impact": _xml_text(event, "impact"),
                "forecast": _xml_text(event, "forecast"),
                "previous": _xml_text(event, "previous"),
            }
        )
    return _parse_faireconomy_items(items, event_type, asof)


def _xml_text(event: Any, name: str) -> str | None:
    child = event.find(name)
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _xml_datetime(event: Any) -> str | None:
    date_text = _xml_text(event, "date")
    time_text = _xml_text(event, "time")
    if not date_text:
        return None
    raw = f"{date_text} {time_text or '12:00am'}"
    try:
        parsed = datetime.strptime(raw, "%m-%d-%Y %I:%M%p").replace(tzinfo=UTC)
        return parsed.isoformat()
    except ValueError:
        return None


def _parse_offset_datetime(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_value(value: Any) -> float | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    multiplier = 1.0
    if raw.upper().endswith("K"):
        multiplier = 1000.0
    elif raw.upper().endswith("M"):
        multiplier = 1_000_000.0
    match = re.search(r"-?\d+(?:\.\d+)?", raw.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0)) * multiplier
    except ValueError:
        return None


def _parse_faireconomy_items(
    items: list[dict[str, Any]],
    event_type: str,
    asof: datetime,
) -> tuple[list[dict[str, Any]], dict[str, float | None], int]:
    keywords = EVENT_KEYWORDS.get(event_type, [event_type.lower()])
    hits: list[dict[str, Any]] = []
    consensus_candidates: list[float] = []
    previous_candidates: list[float] = []
    for raw in items:
        country = str(raw.get("country") or "").upper()
        if country not in {"USD", "US", "UNITED STATES"}:
            continue
        title = clean_text(str(raw.get("title") or ""))
        title_lower = title.lower()
        if not any(keyword in title_lower for keyword in keywords):
            continue
        event_dt = _parse_offset_datetime(str(raw.get("date") or ""))
        forecast = _parse_value(raw.get("forecast"))
        previous = _parse_value(raw.get("previous"))
        if forecast is not None:
            consensus_candidates.append(forecast)
        if previous is not None:
            previous_candidates.append(previous)
        hits.append(
            {
                "keyword": event_type.lower(),
                "title": title,
                "currency": country,
                "importance": raw.get("impact"),
                "event_time": event_dt.isoformat() if event_dt else None,
                "event_time_utc": event_dt.astimezone(UTC).isoformat() if event_dt else None,
                "event_time_et": event_dt.astimezone(ET).isoformat() if event_dt else None,
                "forecast_raw": raw.get("forecast"),
                "previous_raw": raw.get("previous"),
                "snippet": f"{title}; impact={raw.get('impact')}; forecast={raw.get('forecast')}; previous={raw.get('previous')}",
            }
        )
    parsed_values: dict[str, float | None] = {
        "actual": None,
        "consensus": consensus_candidates[0] if consensus_candidates else None,
        "previous": previous_candidates[0] if previous_candidates else None,
    }
    active_hits = [
        item for item in hits
        if _is_near_asof(item.get("event_time_utc"), asof)
    ]
    return (active_hits or hits)[:6], parsed_values, len(hits)


def _is_near_asof(value: Any, asof: datetime) -> bool:
    if not value:
        return True
    event_dt = _parse_offset_datetime(str(value))
    if not event_dt:
        return True
    delta = abs((event_dt.astimezone(UTC) - asof.astimezone(UTC)).total_seconds())
    return delta <= 10 * 24 * 3600


def _write_cache(path: Any, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError:
        return


def _read_cache(path: Any) -> str | None:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        return None
    return None


def _confirmed_value(candidates: list[dict[str, Any]]) -> float | None:
    if len(candidates) < 2:
        return None
    values = [float(item["value"]) for item in candidates if item.get("value") is not None]
    if len(values) < 2:
        return None
    first = values[0]
    if any(abs(value - first) > max(abs(first) * 0.15, 0.05) for value in values[1:]):
        return None
    return round(sum(values) / len(values), 4)
