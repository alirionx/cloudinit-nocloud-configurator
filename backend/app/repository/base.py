"""Backend-independent repository interface (NFR-009, DS-001).

Business logic only uses `Repository`, `Document` and the errors defined here;
it never sees a concrete datastore backend.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class RepositoryError(Exception):
    """Base class for all repository errors."""


class NotFoundError(RepositoryError):
    """The document does not exist."""


class ConflictError(RepositoryError):
    """The document was changed concurrently: the given revision is stale (DS-003)."""


class DatastoreUnavailableError(RepositoryError):
    """The datastore cannot be reached or answered unexpectedly."""


@dataclass(frozen=True)
class Document:
    """A stored document.

    `id` is an application-generated UUID (DS-002). `revision` is an opaque string
    that changes on every update and is used for optimistic locking (DS-003).
    """

    id: str
    revision: str
    created_at: datetime
    modified_at: datetime
    data: dict[str, Any]


class Repository(ABC):
    """Stores documents of one collection (the saved configurations)."""

    @abstractmethod
    async def get(self, document_id: str) -> Document:
        """Return the document or raise `NotFoundError`."""

    @abstractmethod
    async def list(self) -> list[Document]:
        """Return all documents, oldest first."""

    @abstractmethod
    async def create(self, data: dict[str, Any]) -> Document:
        """Store a new document under a newly generated ID."""

    @abstractmethod
    async def update(self, document_id: str, data: dict[str, Any], revision: str) -> Document:
        """Replace the data of a document.

        Raises `NotFoundError` if it does not exist and `ConflictError` if `revision`
        is not the current revision.
        """

    @abstractmethod
    async def delete(self, document_id: str) -> None:
        """Delete a document permanently (NFR-012) or raise `NotFoundError`."""

    @abstractmethod
    async def check(self) -> None:
        """Readiness check (DS-006): raise if the datastore is not usable."""

    async def close(self) -> None:  # noqa: B027 - optional hook
        """Release resources such as connections."""


def new_document_id() -> str:
    return str(uuid.uuid4())


def is_valid_document_id(document_id: str) -> bool:
    """IDs are UUIDs; anything else cannot exist (and must not reach a backend's
    special endpoints, such as CouchDB's `_all_docs`)."""
    try:
        return str(uuid.UUID(document_id)) == document_id
    except ValueError:
        return False


def next_revision(revision: str | None = None) -> str:
    """Revision in the form `<counter>-<random>`, like CouchDB's `_rev`."""
    counter = int(revision.split("-", 1)[0]) if revision else 0
    return f"{counter + 1}-{uuid.uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(UTC)
