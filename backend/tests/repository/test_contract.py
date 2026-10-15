"""Repository contract tests, run against TinyDB and CouchDB alike (DS-007)."""

import uuid

import anyio
import pytest

from app.repository import ConflictError, NotFoundError, Repository

pytestmark = pytest.mark.anyio

SAMPLE = {
    "name": "web-01",
    "basics": {"hostname": "web-01", "locale": "de_DE.UTF-8"},
    "packages": ["git", "wget"],
    "note": "Unicode: äöü ✓",
    "nested": {"list": [1, 2.5, True, None]},
}


async def test_create_returns_document_with_generated_uuid(repository: Repository):
    """DS-001, DS-002: create stores the data under an application-generated UUID."""
    doc = await repository.create(SAMPLE)
    assert str(uuid.UUID(doc.id)) == doc.id
    assert doc.revision
    assert doc.data == SAMPLE
    assert doc.created_at == doc.modified_at
    assert doc.created_at.tzinfo is not None


async def test_internal_backend_fields_are_not_exposed(repository: Repository):
    """DS-002: backend internals (TinyDB doc_id, CouchDB _id/_rev) never leak into data."""
    created = await repository.create(SAMPLE)
    for doc in (created, await repository.get(created.id), *(await repository.list())):
        assert doc.data == SAMPLE
        assert not isinstance(doc.id, int)


async def test_get_returns_stored_document(repository: Repository):
    """DS-001: get returns exactly what was stored."""
    created = await repository.create(SAMPLE)
    assert await repository.get(created.id) == created


@pytest.mark.parametrize("document_id", [str(uuid.uuid4()), "not-a-uuid", "_all_docs", "1", ""])
async def test_get_unknown_id_raises_not_found(repository: Repository, document_id: str):
    """DS-001: unknown or malformed IDs raise NotFoundError (maps to HTTP 404)."""
    with pytest.raises(NotFoundError):
        await repository.get(document_id)


async def test_list_is_empty_initially(repository: Repository):
    """DS-001: a new datastore contains no documents."""
    assert await repository.list() == []


async def test_list_returns_all_documents_oldest_first(repository: Repository):
    """DS-001: list returns every stored document, oldest first."""
    first = await repository.create({"name": "a"})
    second = await repository.create({"name": "b"})
    third = await repository.create({"name": "c"})
    assert [doc.id for doc in await repository.list()] == [first.id, second.id, third.id]


async def test_update_with_current_revision(repository: Repository):
    """DS-001, DS-003: update replaces the data and issues a new revision."""
    created = await repository.create(SAMPLE)
    await anyio.sleep(0.01)
    updated = await repository.update(created.id, {"name": "web-02"}, created.revision)
    assert updated.id == created.id
    assert updated.data == {"name": "web-02"}
    assert updated.revision != created.revision
    assert updated.created_at == created.created_at
    assert updated.modified_at > created.modified_at
    assert await repository.get(created.id) == updated


async def test_update_with_stale_revision_raises_conflict(repository: Repository):
    """DS-003: a concurrent change is detected instead of silently overwritten."""
    created = await repository.create(SAMPLE)
    await repository.update(created.id, {"name": "first writer"}, created.revision)
    with pytest.raises(ConflictError):
        await repository.update(created.id, {"name": "second writer"}, created.revision)
    assert (await repository.get(created.id)).data == {"name": "first writer"}


async def test_update_with_malformed_revision_raises_conflict(repository: Repository):
    """DS-003: an invalid revision string is treated like a stale one."""
    created = await repository.create(SAMPLE)
    with pytest.raises(ConflictError):
        await repository.update(created.id, {"name": "x"}, "garbage")


async def test_update_unknown_id_raises_not_found(repository: Repository):
    """DS-001: updating a missing document raises NotFoundError."""
    with pytest.raises(NotFoundError):
        await repository.update(str(uuid.uuid4()), SAMPLE, "1-abc")


async def test_delete_removes_document_permanently(repository: Repository):
    """DS-001, NFR-012: a deleted document is gone from get and list."""
    keep = await repository.create({"name": "keep"})
    gone = await repository.create({"name": "gone"})
    await repository.delete(gone.id)
    with pytest.raises(NotFoundError):
        await repository.get(gone.id)
    assert [doc.id for doc in await repository.list()] == [keep.id]


async def test_delete_unknown_id_raises_not_found(repository: Repository):
    """DS-001: deleting a missing document raises NotFoundError."""
    with pytest.raises(NotFoundError):
        await repository.delete(str(uuid.uuid4()))


async def test_deleted_document_cannot_be_updated(repository: Repository):
    """DS-001: a deleted document cannot be revived by an update."""
    created = await repository.create(SAMPLE)
    await repository.delete(created.id)
    with pytest.raises(NotFoundError):
        await repository.update(created.id, SAMPLE, created.revision)


async def test_returned_data_is_a_copy(repository: Repository):
    """DS-001: mutating input or returned data does not change the stored document."""
    data = {"packages": ["git"]}
    created = await repository.create(data)
    data["packages"].append("mutated-input")
    created.data["packages"].append("mutated-output")
    assert (await repository.get(created.id)).data == {"packages": ["git"]}


async def test_check_passes_on_healthy_datastore(repository: Repository):
    """DS-006: the readiness check passes when the datastore is usable."""
    await repository.check()
