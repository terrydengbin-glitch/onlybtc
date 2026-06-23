from __future__ import annotations

import asyncio
from typing import Any

from onlybtc.core.glassnode_entitlement import (
    run_glassnode_entitlement_audit,
    write_glassnode_entitlement_report,
)


def main() -> None:
    payload = generate()
    print(payload["json_path"])
    print(payload["md_path"])


def generate(mode: str = "dry_run") -> dict[str, Any]:
    report = asyncio.run(run_glassnode_entitlement_audit(mode=mode))
    return write_glassnode_entitlement_report(report)


if __name__ == "__main__":
    main()
