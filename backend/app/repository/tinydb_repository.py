"""TinyDB backend: a JSON file for development and single-instance setups (section 8.3).

Only one process may use the file (R-02). Within the process, all access is
serialized by a lock and runs in a worker thread so it does not block the event loop.
"""

import copy
import threading
from collections.abc import Callable
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

import anyio.to_thread
from tinydb import Query, TinyDB

from app.repository.base import (
    ConflictError,
    Document,
    NotFoundError,
    Repository,
    is_valid_document_id,
    new_document_id,
    next_revision,
    utc_now,
)

TABLE = "configurations"


class TinyDBRepository(Repository):
    def __init__(self, path: Path) -> None:
        # Fails at startup if the file cannot be created or read (DS-004).
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = TinyDB(path, encoding="utf-8")
        self._table = self._db.table(TABLE)
        self._lock = threading.Lock()

    async def _run[T](self, func: Callable[..., T], *args: Any) -> T:
        def locked() -> T:
            with self._lock:
                return func(*args)

        return await anyio.to_thread.run_sync(partial(locked))

    def _find(self, document_id: str) -> dict[str, Any]:
        record = (
            self._table.get(Query().id == document_id)
            if is_valid_document_id(document_id)
            else None
        )
        if record is None:
            raise NotFoundError(document_id)
        return record

    async def get(self, document_id: str) -> Document:
        return _to_document(await self._run(self._find, document_id))

    async def list(self) -> list[Document]:
        records = await self._run(self._table.all)
        documents = [_to_document(record) for record in records]
        return sorted(documents, key=lambda doc: (doc.created_at, doc.id))

    async def create(self, data: dict[str, Any]) -> Document:
        now = utc_now().isoformat()
        record = {
            "id": new_document_id(),
            "revision": next_revision(),
            "created_at": now,
            "modified_at": now,
            "data": copy.deepcopy(data),
        }
        await self._run(self._table.insert, record)
        return _to_document(record)

    async def update(self, document_id: str, data: dict[str, Any], revision: str) -> Document:
        def update_locked() -> dict[str, Any]:
            record = dict(self._find(document_id))
            if record["revision"] != revision:
                raise ConflictError(document_id)
            record.update(
                revision=next_revision(revision),
                modified_at=utc_now().isoformat(),
                data=copy.deepcopy(data),
            )
            self._table.update(record, Query().id == document_id)
            return record

        return _to_document(await self._run(update_locked))

    async def delete(self, document_id: str) -> None:
        def delete_locked() -> None:
            self._find(document_id)
            self._table.remove(Query().id == document_id)

        await self._run(delete_locked)

    async def check(self) -> None:
        await self._run(len, self._table)

    async def close(self) -> None:
        await self._run(self._db.close)


def _to_document(record: dict[str, Any]) -> Document:
    # TinyDB's internal doc_id is never exposed (DS-002).
    return Document(
        id=record["id"],
        revision=record["revision"],
        created_at=datetime.fromisoformat(record["created_at"]),
        modified_at=datetime.fromisoformat(record["modified_at"]),
        data=copy.deepcopy(record["data"]),
    )
