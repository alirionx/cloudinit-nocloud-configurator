"""CouchDB backend for production via its HTTP API (section 8.3).

Optimistic locking uses CouchDB's document revisions (`_rev`, DS-003).
"""

import asyncio
import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx2

from app.repository.base import (
    ConflictError,
    DatastoreUnavailableError,
    Document,
    NotFoundError,
    Repository,
    is_valid_document_id,
    new_document_id,
    utc_now,
)

logger = logging.getLogger(__name__)

DELETE_ATTEMPTS = 3


class CouchDBRepository(Repository):
    def __init__(
        self,
        url: str,
        user: str,
        password: str,
        database: str,
        timeout: float = 5.0,
    ) -> None:
        # Credentials are sent via basic auth, never as part of the URL (NFR-007).
        self._client = httpx2.AsyncClient(
            base_url=url.rstrip("/"), auth=(user, password), timeout=timeout
        )
        self._database = database
        self._db_path = "/" + quote(database, safe="")

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx2.Response:
        try:
            return await self._client.request(method, self._db_path + path, **kwargs)
        except httpx2.HTTPError as exc:
            raise DatastoreUnavailableError(type(exc).__name__) from exc

    async def _get_raw(self, document_id: str) -> dict[str, Any]:
        if not is_valid_document_id(document_id):
            raise NotFoundError(document_id)
        response = await self._request("GET", f"/{document_id}")
        if response.status_code == 404:
            raise NotFoundError(document_id)
        _expect(response, 200)
        return response.json()

    async def ensure_database(self) -> None:
        """Create the database if it is missing (DS-005)."""
        response = await self._request("GET", "")
        if response.status_code == 404:
            response = await self._request("PUT", "")
            # 412: created concurrently by another replica.
            if response.status_code != 412:
                _expect(response, 201, 202)
            logger.info("Created CouchDB database '%s'", self._database)
        else:
            _expect(response, 200)

    async def get(self, document_id: str) -> Document:
        return _to_document(await self._get_raw(document_id))

    async def list(self) -> list[Document]:
        response = await self._request("GET", "/_all_docs", params={"include_docs": "true"})
        _expect(response, 200)
        documents = [
            _to_document(row["doc"])
            for row in response.json()["rows"]
            if not row["id"].startswith("_design/")
        ]
        return sorted(documents, key=lambda doc: (doc.created_at, doc.id))

    async def create(self, data: dict[str, Any]) -> Document:
        document_id = new_document_id()
        now = utc_now().isoformat()
        body = {"created_at": now, "modified_at": now, "data": data}
        response = await self._request("PUT", f"/{document_id}", json=body)
        _expect(response, 201, 202)
        return _to_document({**body, "_id": document_id, "_rev": response.json()["rev"]})

    async def update(self, document_id: str, data: dict[str, Any], revision: str) -> Document:
        current = await self._get_raw(document_id)
        body = {
            "_rev": revision,
            "created_at": current["created_at"],
            "modified_at": utc_now().isoformat(),
            "data": data,
        }
        response = await self._request("PUT", f"/{document_id}", json=body)
        if response.status_code in (400, 409):
            # 400: malformed revision string, 409: stale revision.
            raise ConflictError(document_id)
        _expect(response, 201, 202)
        return _to_document({**body, "_id": document_id, "_rev": response.json()["rev"]})

    async def delete(self, document_id: str) -> None:
        # Deletion is unconditional; retry if the document changes in between.
        for _ in range(DELETE_ATTEMPTS):
            current = await self._get_raw(document_id)
            response = await self._request(
                "DELETE", f"/{document_id}", params={"rev": current["_rev"]}
            )
            if response.status_code != 409:
                _expect(response, 200, 202)
                return
            await asyncio.sleep(0.05)
        raise ConflictError(document_id)

    async def check(self) -> None:
        # Also retries database creation if CouchDB was unavailable at startup.
        await self.ensure_database()

    async def close(self) -> None:
        await self._client.aclose()


def _expect(response: httpx2.Response, *status_codes: int) -> None:
    if response.status_code not in status_codes:
        # The response body is not included; it may echo document content (NFR-007).
        raise DatastoreUnavailableError(
            f"CouchDB answered {response.request.method} with HTTP {response.status_code}"
        )


def _to_document(raw: dict[str, Any]) -> Document:
    # CouchDB's internal fields (`_id`, `_rev`) are mapped to backend-independent ones.
    return Document(
        id=raw["_id"],
        revision=raw["_rev"],
        created_at=datetime.fromisoformat(raw["created_at"]),
        modified_at=datetime.fromisoformat(raw["modified_at"]),
        data=raw["data"],
    )
