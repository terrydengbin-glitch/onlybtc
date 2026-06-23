from __future__ import annotations

from typing import Any

import onlybtc.api.app as app_module


def test_startup_hook_schedules_daemon_bootstrap_thread(monkeypatch) -> None:
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

    thread = app_module._start_daemon_bootstrap_thread()

    assert starts == [
        ("onlybtc-api-daemon-bootstrap", True),
        ("started", True),
    ]
    assert thread.name == "onlybtc-api-daemon-bootstrap"


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
