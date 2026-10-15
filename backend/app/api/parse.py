"""FR-014: apply hand-edited YAML to the configuration ("Edit as YAML")."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.configurations.model import Configuration
from app.configurations.parsing import parse_file
from app.configurations.service import prepare_for_save
from app.configurations.yaml_input import MAX_YAML_BYTES

router = APIRouter(prefix="/api", tags=["preview"])


class ParseRequest(BaseModel):
    configuration: Configuration = Field(description="The current (possibly unsaved) form state.")
    file: Literal["user-data", "meta-data", "network-config", "vendor-data"]
    content: str = Field(max_length=MAX_YAML_BYTES, description="The edited YAML.")


class ParseResponse(BaseModel):
    configuration: Configuration
    notices: list[str] = Field(
        description="Keys that are kept as additional settings because the form cannot show them."
    )


@router.post(
    "/parse",
    responses={422: {"description": "YAML syntax errors or invalid values, with line numbers."}},
)
async def parse(request: ParseRequest) -> ParseResponse:
    """Parse one edited file back into the configuration model (form <-> YAML round trip).

    Unknown keys are kept as additional settings. Nothing is saved. YAML errors are
    answered with HTTP 422; each error has a line number (`line`) if known.
    """
    result = parse_file(prepare_for_save(request.configuration), request.file, request.content)
    return ParseResponse(configuration=result.configuration, notices=result.notices)
