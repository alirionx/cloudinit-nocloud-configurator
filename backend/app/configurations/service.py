"""Business logic for managing configurations (FR-015).

Uses only the repository interface (NFR-009). Stores the structured model,
never the rendered YAML (section 6).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.configurations.checks import Issue, check
from app.configurations.model import NAME_MAX_LENGTH, Configuration, suggest_instance_id
from app.configurations.sections.users import hash_password
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
        document = await self._repository.create(_to_data(prepare_for_save(configuration)))
        return _from_document(document)

    async def update(
        self, configuration_id: str, configuration: Configuration, revision: str
    ) -> StoredConfiguration:
        document = await self._repository.update(
            configuration_id, _to_data(prepare_for_save(configuration)), revision
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


class ConfigurationInvalidError(Exception):
    """Cross-field rules are violated (see `checks`); maps to HTTP 422."""

    def __init__(self, issues: list[Issue]) -> None:
        super().__init__(f"{len(issues)} invalid field(s)")
        self.issues = issues


def prepare_for_save(configuration: Configuration) -> Configuration:
    """Complete and check a configuration before it is stored, previewed or rendered.

    - FR-005: suggest an instance-id when none was entered.
    - FR-010: hash plain-text passwords; the plain text is discarded (NFR-007).
    - Cross-field errors raise `ConfigurationInvalidError`.
    """
    config = configuration
    if not config.basics.instance_id:
        basics = config.basics.model_copy(
            update={"instance_id": suggest_instance_id(config.basics.hostname)}
        )
        config = config.model_copy(update={"basics": basics})

    if any(user.password for user in config.users.users):
        users = [
            user.model_copy(
                update={
                    "password_hash": hash_password(user.password.get_secret_value()),
                    "password": None,
                }
            )
            if user.password
            else user
            for user in config.users.users
        ]
        config = config.model_copy(
            update={"users": config.users.model_copy(update={"users": users})}
        )

    if errors := check(config).errors:
        raise ConfigurationInvalidError(errors)
    return config


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
