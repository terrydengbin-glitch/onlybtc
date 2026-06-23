from __future__ import annotations

import json

from onlybtc.radar_runtime.audit_report import generate_radar_runtime_audit_report


def generate() -> dict[str, object]:
    return generate_radar_runtime_audit_report(refresh_mode="manual_script")


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
