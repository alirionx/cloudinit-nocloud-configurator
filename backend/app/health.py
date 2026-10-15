"""Liveness and readiness endpoints (NFR-004).

Readiness is the result of all registered checks. Components such as the
datastore (DS-006) register a check via `register_readiness_check`.
"""

import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# A readiness check raises an exception if its component is not ready.
ReadinessCheck = Callable[[], Awaitable[None]]

router = APIRouter(tags=["health"])


def register_readiness_check(app: FastAPI, name: str, check: ReadinessCheck) -> None:
    app.state.readiness_checks[name] = check


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness: the process is running and serving requests."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    """Readiness: all registered checks pass; otherwise HTTP 503."""
    checks: dict[str, ReadinessCheck] = request.app.state.readiness_checks
    results: dict[str, str] = {}
    for name, check in checks.items():
        try:
            await check()
            results[name] = "ok"
        except Exception as exc:
            # Only the exception type is logged; messages may contain credentials (NFR-007).
            logger.warning("Readiness check '%s' failed: %s", name, type(exc).__name__)
            results[name] = "failed"
    ready = all(result == "ok" for result in results.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ok" if ready else "unavailable", "checks": results},
    )
