"""REST API for configurations (FR-004, FR-015).

Invalid input is answered with HTTP 422 and field-level errors (FastAPI default),
unknown IDs with 404, stale revisions with 409 (DS-003).
"""

import logging
from datetime import datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from app.api.preview import PreviewResponse, RenderedFiles, preview_of
from app.configurations.model import Configuration
from app.configurations.rendering import render_files
from app.configurations.service import ConfigurationService, SortKey, StoredConfiguration
from app.images import MEDIA_TYPES, ImageBuildError, ImageFormat, build_image, image_file_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/configurations", tags=["configurations"])


def get_service(request: Request) -> ConfigurationService:
    return ConfigurationService(request.app.state.repository)


Service = Annotated[ConfigurationService, Depends(get_service)]


class ConfigurationResponse(Configuration):
    id: str = Field(description="Application-generated UUID.")
    revision: str = Field(description="Current revision; send it back on update (DS-003).")
    created_at: datetime
    modified_at: datetime

    @classmethod
    def of(cls, stored: StoredConfiguration) -> Self:
        return cls(
            id=stored.id,
            revision=stored.revision,
            created_at=stored.created_at,
            modified_at=stored.modified_at,
            **stored.configuration.model_dump(),
        )


class ConfigurationUpdate(Configuration):
    revision: str = Field(
        min_length=1, description="Revision the changes are based on (from the last read)."
    )
    # Read-only fields: accepted so that a GET response can be sent back unchanged.
    id: str | None = Field(default=None, description="Read-only; must match the URL if sent.")
    created_at: datetime | None = Field(default=None, description="Read-only; ignored.")
    modified_at: datetime | None = Field(default=None, description="Read-only; ignored.")

    def configuration(self) -> Configuration:
        # Built from the validated values, not via model_dump(): dumping would drop
        # write-only fields such as new plain-text passwords (FR-010).
        return Configuration(**{name: getattr(self, name) for name in Configuration.model_fields})


class ConfigurationSummary(BaseModel):
    """FR-015: entry in the configuration list (UI-02)."""

    id: str
    name: str
    hostname: str | None
    created_at: datetime
    modified_at: datetime

    @classmethod
    def of(cls, stored: StoredConfiguration) -> Self:
        return cls(
            id=stored.id,
            name=stored.configuration.name,
            hostname=stored.configuration.basics.hostname,
            created_at=stored.created_at,
            modified_at=stored.modified_at,
        )


def _created(stored: StoredConfiguration, response: Response) -> ConfigurationResponse:
    response.headers["Location"] = f"{router.prefix}/{stored.id}"
    return ConfigurationResponse.of(stored)


@router.get("", response_model=list[ConfigurationSummary])
async def list_configurations(
    service: Service,
    search: Annotated[
        str | None, Query(max_length=200, description="Filter by name or hostname.")
    ] = None,
    sort: Annotated[SortKey, Query(description="Sort field; '-' prefix for descending.")] = (
        "-modified_at"
    ),
) -> list[ConfigurationSummary]:
    return [ConfigurationSummary.of(item) for item in await service.list(search, sort)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_configuration(
    configuration: Configuration, service: Service, response: Response
) -> ConfigurationResponse:
    return _created(await service.create(configuration), response)


@router.get("/{configuration_id}")
async def get_configuration(configuration_id: str, service: Service) -> ConfigurationResponse:
    return ConfigurationResponse.of(await service.get(configuration_id))


@router.put(
    "/{configuration_id}",
    responses={409: {"description": "The configuration was changed in the meantime."}},
)
async def update_configuration(
    configuration_id: str, update: ConfigurationUpdate, service: Service
) -> ConfigurationResponse:
    if update.id is not None and update.id != configuration_id:
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "loc": ["body", "id"],
                    "msg": "does not match the configuration ID in the URL",
                    "type": "value_error",
                }
            ],
        )
    stored = await service.update(configuration_id, update.configuration(), update.revision)
    return ConfigurationResponse.of(stored)


@router.delete("/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_configuration(configuration_id: str, service: Service) -> None:
    await service.delete(configuration_id)


@router.post("/{configuration_id}/duplicate", status_code=status.HTTP_201_CREATED)
async def duplicate_configuration(
    configuration_id: str, service: Service, response: Response
) -> ConfigurationResponse:
    return _created(await service.duplicate(configuration_id), response)


@router.get("/{configuration_id}/files")
async def get_files(configuration_id: str, service: Service) -> RenderedFiles:
    """The rendered NoCloud files of a saved configuration (FR-001)."""
    stored = await service.get(configuration_id)
    return RenderedFiles.model_validate(render_files(stored.configuration))


@router.get("/{configuration_id}/preview")
async def get_preview(configuration_id: str, service: Service) -> PreviewResponse:
    """Files and warnings of a saved configuration (FR-013)."""
    return preview_of((await service.get(configuration_id)).configuration)


@router.get(
    "/{configuration_id}/image",
    response_class=Response,
    responses={
        200: {
            "description": "The seed image as a file download.",
            "content": {"application/octet-stream": {}, "application/x-iso9660-image": {}},
        },
        500: {"description": "Image generation failed."},
    },
)
async def download_image(
    configuration_id: str,
    service: Service,
    image_format: Annotated[
        ImageFormat, Query(alias="format", description="Image format.")
    ] = ImageFormat.ISO,
) -> Response:
    """FR-002, FR-003: generate the seed image on the fly and deliver it directly.

    Nothing is stored; temporary files are removed before the response is sent.
    """
    stored = await service.get(configuration_id)
    try:
        content = await build_image(render_files(stored.configuration), image_format)
    except ImageBuildError as exc:
        logger.error("Image generation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Image generation failed.") from exc
    file_name = image_file_name(stored.configuration.name, image_format)
    return Response(
        content=content,
        media_type=MEDIA_TYPES[image_format],
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Cache-Control": "no-store",
        },
    )
