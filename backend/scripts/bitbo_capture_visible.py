from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import Response, async_playwright


ROOT = Path(__file__).resolve().parents[2]
PROFILE_DIR = ROOT / "cache" / "playwright-bitbo-profile"
ARTIFACT_DIR = ROOT / "playwright-artifacts"
CAPTURE_PATH = ARTIFACT_DIR / "bitbo-network-capture.json"
SCREENSHOT_PATH = ARTIFACT_DIR / "bitbo-visible-session.png"

TARGET_URLS = [
    "https://charts.bitbo.io/sth-realized-price/",
    "https://charts.bitbo.io/lth-realized-price/",
]


def interesting_url(url: str) -> bool:
    lower = url.lower()
    return any(
        token in lower
        for token in [
            "api",
            "json",
            "csv",
            "xlsx",
            "series",
            "chart",
            "sth",
            "lth",
            "realized",
            "price",
        ]
    )


async def safe_body(response: Response) -> str | None:
    try:
        content_type = response.headers.get("content-type", "")
        if not any(token in content_type.lower() for token in ["json", "csv", "text"]):
            return None
        text = await response.text()
        return text[:20_000]
    except Exception:
        return None


async def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    captures: list[dict[str, Any]] = []

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1600, "height": 950},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else await context.new_page()

        async def on_response(response: Response) -> None:
            if not interesting_url(response.url):
                return
            body = await safe_body(response)
            captures.append(
                {
                    "captured_at": datetime.now(UTC).isoformat(),
                    "url": response.url,
                    "status": response.status,
                    "content_type": response.headers.get("content-type"),
                    "body_sample": body,
                }
            )
            CAPTURE_PATH.write_text(
                json.dumps(captures, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        context.on("response", lambda response: asyncio.create_task(on_response(response)))

        print("Visible Bitbo capture browser opened.")
        print(f"Profile dir: {PROFILE_DIR}")
        print(f"Capture file: {CAPTURE_PATH}")
        print("Please complete the human challenge, then visit both pages:")
        for url in TARGET_URLS:
            print(f"  - {url}")
        print("Close the browser window when finished.")

        await page.goto(TARGET_URLS[0], wait_until="domcontentloaded", timeout=60_000)

        while context.pages:
            await asyncio.sleep(2)
            active = context.pages[-1]
            try:
                await active.screenshot(path=str(SCREENSHOT_PATH), full_page=False)
            except Exception:
                pass

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
