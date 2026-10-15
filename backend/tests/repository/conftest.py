"""Fixtures for the repository contract tests (DS-007).

CouchDB source, in order of preference:
1. An existing server: COUCHDB_TEST_URL, COUCHDB_TEST_USER, COUCHDB_TEST_PASSWORD.
2. A throwaway Docker container (image: COUCHDB_TEST_IMAGE, default couchdb:3).
Without either, CouchDB tests are skipped. Set COUCHDB_TEST_REQUIRED=1 (e.g. in CI)
to fail instead of skipping.
"""

import os
import shutil
import subprocess
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx2
import pytest

from app.repository import Repository
from app.repository.couchdb_repository import CouchDBRepository
from app.repository.tinydb_repository import TinyDBRepository


@dataclass(frozen=True)
class CouchDBServer:
    url: str
    user: str
    password: str


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _unavailable(reason: str) -> None:
    if os.environ.get("COUCHDB_TEST_REQUIRED") == "1":
        pytest.fail(f"CouchDB required but unavailable: {reason}")
    pytest.skip(f"CouchDB unavailable: {reason}")


def _wait_until_up(server: CouchDBServer, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx2.get(f"{server.url}/_up", timeout=2).status_code == 200:
                return
        except httpx2.HTTPError:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"CouchDB at {server.url} did not come up within {timeout}s")


@pytest.fixture(scope="session")
def couchdb_server() -> Iterator[CouchDBServer]:
    if url := os.environ.get("COUCHDB_TEST_URL"):
        yield CouchDBServer(
            url=url.rstrip("/"),
            user=os.environ.get("COUCHDB_TEST_USER", "admin"),
            password=os.environ.get("COUCHDB_TEST_PASSWORD", ""),
        )
        return

    docker = shutil.which("docker")
    if docker is None or subprocess.run([docker, "version"], capture_output=True).returncode:
        _unavailable("set COUCHDB_TEST_URL or make Docker available")

    password = uuid.uuid4().hex
    image = os.environ.get("COUCHDB_TEST_IMAGE", "couchdb:3")
    container = subprocess.run(
        [docker, "run", "-d", "--rm", "-p", "127.0.0.1::5984",
         "-e", "COUCHDB_USER=admin", "-e", f"COUCHDB_PASSWORD={password}", image],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    try:
        port = (
            subprocess.run(
                [docker, "port", container, "5984/tcp"], capture_output=True, text=True, check=True
            )
            .stdout.split(":")[-1]
            .strip()
        )
        server = CouchDBServer(url=f"http://127.0.0.1:{port}", user="admin", password=password)
        _wait_until_up(server)
        yield server
    finally:
        subprocess.run([docker, "rm", "-f", container], capture_output=True)


@pytest.fixture
async def couchdb_repository(couchdb_server: CouchDBServer) -> AsyncIterator[CouchDBRepository]:
    """A repository on a fresh, uniquely named database that is dropped afterwards."""
    database = f"test_{uuid.uuid4().hex}"
    repo = CouchDBRepository(
        url=couchdb_server.url,
        user=couchdb_server.user,
        password=couchdb_server.password,
        database=database,
    )
    await repo.check()
    yield repo
    await repo.close()
    httpx2.delete(
        f"{couchdb_server.url}/{database}", auth=(couchdb_server.user, couchdb_server.password)
    )


@pytest.fixture
async def tinydb_repository(tmp_path: Path) -> AsyncIterator[TinyDBRepository]:
    repo = TinyDBRepository(tmp_path / "db.json")
    yield repo
    await repo.close()


@pytest.fixture(params=["tinydb", "couchdb"])
def repository(request: pytest.FixtureRequest) -> Repository:
    """The same contract tests run against every backend (DS-007)."""
    return request.getfixturevalue(f"{request.param}_repository")
