"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from app import health
from app.api import configurations
from app.repository import (
    ConflictError,
    DatastoreUnavailableError,
    NotFoundError,
    Repository,
    create_repository,
)
from app.settings import Settings

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, repository: Repository | None = None) -> FastAPI:
    """Build the app. `repository` overrides the one selected by the settings (tests)."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # An unusable datastore configuration aborts startup here (DS-004).
        repo = repository or create_repository(settings)
        app.state.repository = repo
        health.register_readiness_check(app, "datastore", repo.check)
        if settings.datastore_backend == "tinydb" and repository is None:
            logger.warning("TinyDB datastore active: run exactly one replica and one worker (R-02)")
        try:
            await repo.check()
        except Exception as exc:
            # Not fatal: the datastore may become available later; /readyz reports it.
            logger.warning("Datastore not ready at startup: %s", type(exc).__name__)
        try:
            yield
        finally:
            await repo.close()

    app = FastAPI(title="cloudinit-nocloud-configurator", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.readiness_checks = {}
    app.include_router(health.router)
    app.include_router(configurations.router)
    _add_error_handlers(app)
    if settings.static_dir is not None:
        # Registered last so that API and health routes take precedence.
        _mount_frontend(app, settings.static_dir)
    return app


def _add_error_handlers(app: FastAPI) -> None:
    """Map backend-independent repository errors to HTTP responses."""

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Configuration not found."})

    @app.exception_handler(ConflictError)
    async def conflict(request: Request, exc: ConflictError) -> JSONResponse:
        # DS-003, FR-015: never overwrite concurrent changes silently.
        return JSONResponse(
            status_code=409,
            content={
                "detail": "The configuration was changed in the meantime. "
                "Reload it and apply your changes again."
            },
        )

    @app.exception_handler(DatastoreUnavailableError)
    async def unavailable(request: Request, exc: DatastoreUnavailableError) -> JSONResponse:
        logger.error("Datastore unavailable: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "Datastore unavailable."})


def _mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Serve the built Vue app; unknown non-API paths fall back to index.html."""
    root = static_dir.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (root / path).resolve()
        if path and candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)
