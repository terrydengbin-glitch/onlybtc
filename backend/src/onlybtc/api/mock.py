from __future__ import annotations

from fastapi import APIRouter

from onlybtc.api.contracts import ok_response
from onlybtc.api.mock_fixtures import (
    P9_C13_MOCK_SCHEMA_VERSION,
    p9_c13_mock_server_manifest,
)

router = APIRouter(prefix="/api/mock", tags=["mock"])


@router.get("/p9-c13/scenarios")
def p9_c13_scenarios() -> dict[str, object]:
    return ok_response(
        p9_c13_mock_server_manifest(),
        schema_version=P9_C13_MOCK_SCHEMA_VERSION,
    )
