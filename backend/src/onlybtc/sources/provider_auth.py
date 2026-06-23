from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from onlybtc.core.paths import paths


@dataclass(frozen=True)
class ProviderAuthConfig:
    provider_id: str
    login_url: str
    verify_url: str
    logged_out_markers: tuple[str, ...]
    authenticated_hosts: tuple[str, ...]


@dataclass(frozen=True)
class ProviderAuthPaths:
    provider_id: str
    auth_dir: Path
    profile_dir: Path
    storage_state_path: Path
    status_path: Path


PROVIDER_AUTH_CONFIGS: dict[str, ProviderAuthConfig] = {
    "glassnode": ProviderAuthConfig(
        provider_id="glassnode",
        login_url="https://studio.glassnode.com/login",
        verify_url="https://studio.glassnode.com/",
        logged_out_markers=("log in", "sign in", "login", "continue with google"),
        authenticated_hosts=("studio.glassnode.com", "app.glassnode.com", "glassnode.com"),
    )
}


def provider_auth_paths(provider_id: str) -> ProviderAuthPaths:
    auth_dir = paths.playwright_artifacts_dir / "auth" / provider_id
    return ProviderAuthPaths(
        provider_id=provider_id,
        auth_dir=auth_dir,
        profile_dir=auth_dir / "profile",
        storage_state_path=auth_dir / "storage-state.json",
        status_path=auth_dir / "status.json",
    )


def get_provider_auth_config(provider_id: str) -> ProviderAuthConfig:
    try:
        return PROVIDER_AUTH_CONFIGS[provider_id]
    except KeyError as exc:
        supported = ", ".join(sorted(PROVIDER_AUTH_CONFIGS))
        raise ValueError(f"Unsupported provider_id: {provider_id}. Supported: {supported}") from exc


async def bootstrap_provider_login(
    provider_id: str,
    timeout_seconds: int = 600,
    manual_confirm: bool = False,
) -> dict[str, Any]:
    config = get_provider_auth_config(provider_id)
    auth_paths = provider_auth_paths(provider_id)
    auth_paths.auth_dir.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright is not installed; run `python -m playwright install chromium`"
        ) from exc

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(auth_paths.profile_dir),
            headless=False,
            viewport={"width": 1440, "height": 1000},
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(config.login_url, wait_until="domcontentloaded", timeout=45_000)
        if manual_confirm:
            await asyncio.wait_for(
                asyncio.to_thread(
                    input,
                    (
                        f"Login to {provider_id} in the opened browser, then press Enter here "
                        "to save the local session..."
                    ),
                ),
                timeout=timeout_seconds,
            )
        else:
            try:
                await _wait_until_authenticated(page, config, timeout_seconds)
            except Exception as exc:  # noqa: BLE001
                await context.close()
                return _write_auth_status(
                    provider_id=provider_id,
                    status_path=auth_paths.status_path,
                    configured=auth_paths.storage_state_path.exists(),
                    verified=False,
                    title=None,
                    current_url=None,
                    message=f"login was not completed: {type(exc).__name__}",
                )
        await context.storage_state(path=str(auth_paths.storage_state_path))
        title = await page.title()
        current_url = _safe_url(page.url)
        await context.close()

    status = _write_auth_status(
        provider_id=provider_id,
        status_path=auth_paths.status_path,
        configured=True,
        verified=False,
        title=title,
        current_url=current_url,
        message="storage state saved; run provider-auth-status to verify",
    )
    return {
        "provider_id": provider_id,
        "configured": True,
        "verified": False,
        "profile_dir": str(auth_paths.profile_dir),
        "storage_state_path": str(auth_paths.storage_state_path),
        "status": status,
    }


async def verify_provider_login(provider_id: str) -> dict[str, Any]:
    config = get_provider_auth_config(provider_id)
    auth_paths = provider_auth_paths(provider_id)
    if not auth_paths.storage_state_path.exists():
        return _write_auth_status(
            provider_id=provider_id,
            status_path=auth_paths.status_path,
            configured=False,
            verified=False,
            title=None,
            current_url=None,
            message="storage state not found; run provider-login first",
        )

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright is not installed; run `python -m playwright install chromium`"
        ) from exc

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(auth_paths.storage_state_path))
        page = await context.new_page()
        await page.goto(config.verify_url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(2_000)
        title = await page.title()
        current_url = _safe_url(page.url)
        body_text = (await page.locator("body").inner_text(timeout=10_000)).lower()
        await browser.close()

    verified = _page_looks_authenticated(current_url, body_text, config)
    return _write_auth_status(
        provider_id=provider_id,
        status_path=auth_paths.status_path,
        configured=True,
        verified=verified,
        title=title,
        current_url=current_url,
        message="authenticated" if verified else "login markers detected; session may be expired",
    )


def auth_status(provider_id: str) -> dict[str, Any]:
    auth_paths = provider_auth_paths(provider_id)
    if not auth_paths.status_path.exists():
        return {
            "provider_id": provider_id,
            "configured": auth_paths.storage_state_path.exists(),
            "verified": False,
            "status_path": str(auth_paths.status_path),
            "message": "status not found",
        }
    return _load_json(auth_paths.status_path)


async def _wait_until_authenticated(
    page: Any,
    config: ProviderAuthConfig,
    timeout_seconds: int,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        body_text = ""
        try:
            body_text = (await page.locator("body").inner_text(timeout=5_000)).lower()
        except Exception:  # noqa: BLE001
            body_text = ""
        if _page_looks_authenticated(page.url, body_text, config):
            return
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(
                f"Timed out waiting for {config.provider_id} login after {timeout_seconds} seconds"
            )
        await page.wait_for_timeout(2_000)


def _page_looks_authenticated(
    current_url: str,
    body_text: str,
    config: ProviderAuthConfig,
) -> bool:
    if not body_text.strip():
        return False
    parsed = urlparse(current_url)
    if parsed.netloc.lower() not in config.authenticated_hosts:
        return False
    if parsed.path.rstrip("/").endswith("/login"):
        return False
    return not any(marker in body_text for marker in config.logged_out_markers)


def _safe_url(raw_url: str | None) -> str | None:
    if not raw_url:
        return raw_url
    parsed = urlparse(raw_url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _write_auth_status(
    provider_id: str,
    status_path: Path,
    configured: bool,
    verified: bool,
    title: str | None,
    current_url: str | None,
    message: str,
) -> dict[str, Any]:
    import json

    status_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider_id": provider_id,
        "configured": configured,
        "verified": verified,
        "title": title,
        "current_url": current_url,
        "message": message,
        "last_checked_at": datetime.now(UTC).isoformat(),
        "sensitive_fields_saved": False,
    }
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))
