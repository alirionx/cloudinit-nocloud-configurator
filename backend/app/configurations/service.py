"""Business logic for managing configurations (FR-015).

Uses only the repository interface (NFR-009). Stores the structured model,
never the rendered YAML (section 6).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.configurations.model import NAME_MAX_LENGTH, Configuration, suggest_instance_id
from app.repository import Document, Repository

SortKey = Literal["name", "-name", "modified_at", "-modified_at", "created_at", "-created_at"]

COPY_SUFFIX = " (copy)"


@dataclass(frozen=True)
class StoredConfiguration:
    id: str
    revision: str
    created_at: datetime
    modified_at: datetime
    configuration: Configuration


class ConfigurationService:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    async def list(
        self, search: str | None = None, sort: SortKey = "-modified_at"
    ) -> list[StoredConfiguration]:
        items = [_from_document(doc) for doc in await self._repository.list()]
        if search and (needle := search.strip().casefold()):
            items = [item for item in items if needle in _search_text(item)]
        field = sort.removeprefix("-")
        if field == "name":
            items.sort(key=lambda item: (item.configuration.name.casefold(), item.id))
        else:
            items.sort(key=lambda item: (getattr(item, field), item.id))
        if sort.startswith("-"):
            items.reverse()
        return items

    async def get(self, configuration_id: str) -> StoredConfiguration:
        return _from_document(await self._repository.get(configuration_id))

    async def create(self, configuration: Configuration) -> StoredConfiguration:
        document = await self._repository.create(_to_data(_with_instance_id(configuration)))
        return _from_document(document)

    async def update(
        self, configuration_id: str, configuration: Configuration, revision: str
    ) -> StoredConfiguration:
        document = await self._repository.update(
            configuration_id, _to_data(_with_instance_id(configuration)), revision
        )
        return _from_document(document)

    async def delete(self, configuration_id: str) -> None:
        await self._repository.delete(configuration_id)

    async def duplicate(self, configuration_id: str) -> StoredConfiguration:
        """FR-015: copy named "<name> (copy)" with a new ID and a new instance-id."""
        original = (await self.get(configuration_id)).configuration
        name = original.name[: NAME_MAX_LENGTH - len(COPY_SUFFIX)] + COPY_SUFFIX
        basics = original.basics.model_copy(
            update={"instance_id": suggest_instance_id(original.basics.hostname)}
        )
        copy = original.model_copy(update={"name": name, "basics": basics})
        return await self.create(copy)


def _with_instance_id(configuration: Configuration) -> Configuration:
    """FR-005: suggest an instance-id when none was entered."""
    if configuration.basics.instance_id:
        return configuration
    basics = configuration.basics.model_copy(
        update={"instance_id": suggest_instance_id(configuration.basics.hostname)}
    )
    return configuration.model_copy(update={"basics": basics})


def _to_data(configuration: Configuration) -> dict:
    return configuration.model_dump(mode="json")


def _from_document(document: Document) -> StoredConfiguration:
    return StoredConfiguration(
        id=document.id,
        revision=document.revision,
        created_at=document.created_at,
        modified_at=document.modified_at,
        configuration=Configuration.model_validate(document.data),
    )


def _search_text(item: StoredConfiguration) -> str:
    """FR-015: the list is filterable by name and hostname."""
    config = item.configuration
    return f"{config.name}\n{config.basics.hostname or ''}".casefold()
