"""Datastore abstraction (NFR-009, section 8.3)."""

from app.repository.base import (
    ConflictError,
    DatastoreUnavailableError,
    Document,
    NotFoundError,
    Repository,
    RepositoryError,
)
from app.settings import Settings

__all__ = [
    "ConflictError",
    "DatastoreUnavailableError",
    "Document",
    "NotFoundError",
    "Repository",
    "RepositoryError",
    "create_repository",
]


def create_repository(settings: Settings) -> Repository:
    """Create the repository for the backend selected via `DATASTORE_BACKEND`."""
    if settings.datastore_backend == "couchdb":
        from app.repository.couchdb_repository import CouchDBRepository

        # Presence of these values is guaranteed by the settings validation (DS-004).
        assert settings.couchdb_url and settings.couchdb_user and settings.couchdb_password
        return CouchDBRepository(
            url=str(settings.couchdb_url),
            user=settings.couchdb_user,
            password=settings.couchdb_password.get_secret_value(),
            database=settings.couchdb_database,
        )

    from app.repository.tinydb_repository import TinyDBRepository

    return TinyDBRepository(settings.tinydb_path)
