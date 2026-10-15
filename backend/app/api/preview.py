"""Live preview of the YAML files for unsaved form input (FR-013)."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.configurations.checks import Issue, check
from app.configurations.model import Configuration
from app.configurations.rendering import render_files
from app.configurations.schema import SchemaIssue, validate_files
from app.configurations.service import prepare_for_save

router = APIRouter(prefix="/api", tags=["preview"])


class RenderedFiles(BaseModel):
    """The NoCloud files; `null` for optional files without content."""

    model_config = ConfigDict(populate_by_name=True)

    user_data: str = Field(alias="user-data")
    meta_data: str = Field(alias="meta-data")
    network_config: str | None = Field(alias="network-config")
    vendor_data: str | None = Field(alias="vendor-data")


class PreviewResponse(BaseModel):
    files: RenderedFiles
    warnings: list[Issue] = Field(description="Non-blocking hints with the affected field.")
    schema_issues: list[SchemaIssue] = Field(
        description="Violations of the cloud-init JSON schema (NFR-008), with file and line."
    )


def preview_of(configuration: Configuration) -> PreviewResponse:
    files = render_files(configuration)
    return PreviewResponse(
        files=RenderedFiles.model_validate(files),
        warnings=check(configuration).warnings,
        schema_issues=validate_files(files),
    )


@router.post("/preview")
async def preview(configuration: Configuration) -> PreviewResponse:
    """Render the files exactly as saving and downloading would (FR-013).

    Invalid input is answered with HTTP 422 and field-level errors (FR-004).
    """
    return preview_of(prepare_for_save(configuration))
