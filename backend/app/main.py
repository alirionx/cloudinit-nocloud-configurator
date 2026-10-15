"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from app import health, images
from app.api import configurations, defaults, parse, preview
from app.configurations.sections.users import PasswordHashingError
from app.configurations.service import ConfigurationInvalidError
from app.configurations.yaml_input import YamlInputError
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
        health.register_readiness_check(app, "image-tools", _check_image_tools)
        if missing := images.missing_tools():
            logger.error("Image tools missing, downloads will fail: %s", ", ".join(missing))
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
    app.include_router(preview.router)
    app.include_router(defaults.router)
    app.include_router(parse.router)
    _add_error_handlers(app)
    if settings.static_dir is not None:
        # Registered last so that API and health routes take precedence.
        _mount_frontend(app, settings.static_dir)
    return app


async def _check_image_tools() -> None:
    """FR-002: seed images can only be built if all image tools are installed."""
    if missing := images.missing_tools():
        raise RuntimeError(f"missing image tools: {', '.join(missing)}")


def _add_error_handlers(app: FastAPI) -> None:
    """Map backend-independent repository errors to HTTP responses."""

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        """FR-004: field-level errors. Submitted values are never echoed back, because
        they may contain secrets such as plain-text passwords (FR-010, NFR-007)."""
        detail = [
            {
                "loc": list(error["loc"]),
                "msg": str(error["msg"]).removeprefix("Value error, "),
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(ConfigurationInvalidError)
    async def invalid_configuration(
        request: Request, exc: ConfigurationInvalidError
    ) -> JSONResponse:
        """Cross-field errors, in the same format as field validation errors."""
        detail = [
            {"loc": ["body", *issue.loc], "msg": issue.msg, "type": "value_error"}
            for issue in exc.issues
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(YamlInputError)
    async def invalid_yaml(request: Request, exc: YamlInputError) -> JSONResponse:
        """FR-014: YAML errors with line numbers."""
        detail = [
            {
                "loc": ["body", "content", *issue.path],
                "line": issue.line,
                "msg": issue.msg,
                "type": "yaml_error",
            }
            for issue in exc.issues
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(PasswordHashingError)
    async def hashing_failed(request: Request, exc: PasswordHashingError) -> JSONResponse:
        logger.error("Password hashing failed: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "Password hashing failed."})

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
