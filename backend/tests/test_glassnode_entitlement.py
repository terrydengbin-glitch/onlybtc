from __future__ import annotations

import httpx
import pytest

import onlybtc.core.glassnode_entitlement as entitlement
from onlybtc.core.config import Settings


@pytest.mark.asyncio
async def test_glassnode_entitlement_missing_key_is_provider_locked() -> None:
    report = await entitlement.run_glassnode_entitlement_audit(
        settings=Settings(_env_file=None),
        mode="dry_run",
    )

    assert report["schema_version"] == "p10.c08.glassnode_entitlement.v1"
    assert report["overall_status"] == "provider_locked"
    assert report["available_count"] == 0
    assert {item["entitlement_status"] for item in report["items"]} == {"missing_key"}
    assert "secret" not in str(report).lower()
    assert "sessionid=" not in str(report).lower()


@pytest.mark.asyncio
async def test_glassnode_entitlement_available_and_locked_paths(monkeypatch) -> None:
    seen_params: list[dict[str, str]] = []

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def get(self, url: str, **kwargs):
            seen_params.append(kwargs["params"])
            if "price_realized" in url:
                return httpx.Response(200, json=[{"t": 1782172800, "v": 123.4}])
            if "short_term" in url:
                return httpx.Response(403, json={"error": "forbidden"})
            if "long_term" in url:
                return httpx.Response(429, json={"error": "slow down"})
            return httpx.Response(404, json={"error": "missing"})

    monkeypatch.setattr(entitlement.httpx, "AsyncClient", FakeClient)

    report = await entitlement.run_glassnode_entitlement_audit(
        settings=Settings(glassnode_api_key="glassnode-secret-value", _env_file=None),
        mode="dry_run",
    )
    by_metric = {item["metric_id"]: item for item in report["items"]}

    assert by_metric["realized_price"]["entitlement_status"] == "available"
    assert by_metric["realized_price"]["production_write_allowed"] is True
    assert by_metric["sth_cost_basis"]["entitlement_status"] == "unauthorized"
    assert by_metric["lth_cost_basis"]["entitlement_status"] == "rate_limited"
    assert "glassnode-secret-value" not in str(report)
    assert seen_params[0]["api_key"] == "glassnode-secret-value"


@pytest.mark.asyncio
async def test_glassnode_entitlement_schema_changed_is_not_available(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def get(self, url: str, **kwargs):
            return httpx.Response(200, json=[{"unexpected": 1}])

    monkeypatch.setattr(entitlement.httpx, "AsyncClient", FakeClient)

    report = await entitlement.run_glassnode_entitlement_audit(
        settings=Settings(glassnode_api_key="glassnode-secret-value", _env_file=None),
        mode="dry_run",
    )

    assert report["available_count"] == 0
    assert {item["entitlement_status"] for item in report["items"]} == {"schema_changed"}
    assert {item["production_write_allowed"] for item in report["items"]} == {False}


def test_glassnode_entitlement_report_write_and_markdown(tmp_path, monkeypatch) -> None:
    json_path = tmp_path / "glassnode.json"
    md_path = tmp_path / "glassnode.md"
    monkeypatch.setattr(entitlement, "REPORT_JSON", json_path)
    monkeypatch.setattr(entitlement, "REPORT_MD", md_path)

    report = {
        "schema_version": "p10.c08.glassnode_entitlement.v1",
        "generated_at": "2026-06-23T00:00:00+00:00",
        "provider_id": "glassnode",
        "mode": "mock",
        "applied_to_production": False,
        "overall_status": "mock_only",
        "configured": True,
        "available_count": 1,
        "locked_count": 0,
        "guardrails": ["audit_only_no_metric_write"],
        "items": [
            {
                "metric_id": "realized_price",
                "entitlement_status": "available",
                "http_status": 200,
                "quality": 0.85,
                "locked_reason": "",
                "endpoint": "/v1/metrics/market/price_realized_usd",
            }
        ],
        "production_write_candidates": ["realized_price"],
    }

    written = entitlement.write_glassnode_entitlement_report(report)

    assert json_path.exists()
    assert md_path.exists()
    assert written["json_path"] == str(json_path)
    assert entitlement.latest_glassnode_entitlement_report(json_path)["provider_id"] == "glassnode"
