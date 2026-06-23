from fastapi.testclient import TestClient

from onlybtc.api.app import app


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_run_once_endpoint() -> None:
    client = TestClient(app)

    response = client.post("/api/run-once")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert len(body["stages"]) == 12
    assert body["run_entrypoint"] == "legacy_mock"
    assert body["deprecated"] is True
    assert body["production_entrypoint"] == "/api/p45/run-full-with-llm/jobs"


def test_sources_collect_endpoint() -> None:
    client = TestClient(app)

    response = client.post("/api/sources/collect?mode=mock")

    assert response.status_code == 200
    assert response.json()["collected"] >= 5


def test_metric_window_endpoint() -> None:
    client = TestClient(app)
    client.post("/api/sources/collect?mode=mock")

    response = client.get("/api/metrics/btc_price/window?run_mode=mock")

    assert response.status_code == 200
    assert response.json()["metric_id"] == "btc_price"


def test_events_sse_once_endpoint() -> None:
    client = TestClient(app)

    with client.stream("GET", "/api/events?once=true") as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: p45_run_update" in body
    assert '"schema_version": "p9.c10.events.v1"' in body
    assert '"event_type": "p45_run_update"' in body
    assert '"recoverable": true' in body
