from __future__ import annotations

import asyncio
from typing import Any

import onlybtc.api.app as app_module


def test_lifespan_schedules_daemon_bootstrap_thread(monkeypatch) -> None:
    starts: list[tuple[str, bool]] = []

    class FakeThread:
        def __init__(self, *, target, name: str, daemon: bool) -> None:  # noqa: ANN001
            starts.append((name, daemon))
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            starts.append(("started", self.daemon))

    monkeypatch.setattr(app_module, "Thread", FakeThread)

    async def run_lifespan() -> None:
        async with app_module.app_lifespan(app_module.app):
            starts.append(("inside", True))

    asyncio.run(run_lifespan())

    assert starts == [
        ("onlybtc-api-daemon-bootstrap", True),
        ("started", True),
        ("inside", True),
    ]


def test_daemon_bootstrap_continues_after_starter_error() -> None:
    calls: list[str] = []

    def failing_start(*, auto: bool) -> dict[str, Any]:
        calls.append(f"failing:{auto}")
        raise RuntimeError("boom")

    def successful_start(*, auto: bool) -> dict[str, Any]:
        calls.append(f"successful:{auto}")
        return {"status": "ok"}

    app_module._bootstrap_runtime_daemons((failing_start, successful_start))

    assert calls == ["failing:True", "successful:True"]
