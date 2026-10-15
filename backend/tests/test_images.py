"""Seed image generation and download (FR-002, FR-003).

Images are inspected with the same tools cloud-init relies on (blkid for the label)
and read back without mounting. Skipped if the image tools are not installed.
"""

import json
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import images
from app.images import ImageBuildError, ImageFormat, build_image, image_file_name
from app.main import create_app
from app.settings import Settings

pytestmark = pytest.mark.skipif(
    bool(images.missing_tools()) or shutil.which("blkid") is None,
    reason="image tools (xorriso, mtools, dosfstools, qemu-img, blkid) not installed",
)

FILES = {
    "user-data": "#cloud-config\ntimezone: Europe/Berlin\nwrite_files:\n- content: äöü ✓\n",
    "meta-data": "instance-id: iid-test\nlocal-hostname: web-01\n",
    "network-config": None,
    "vendor-data": None,
}


def blkid(path: Path) -> dict[str, str]:
    output = subprocess.run(
        ["blkid", "-p", "-o", "export", str(path)], capture_output=True, text=True, check=True
    ).stdout
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)


def read_iso(path: Path, target: Path) -> dict[str, str]:
    subprocess.run(
        ["xorriso", "-osirrox", "on", "-indev", str(path), "-extract", "/", str(target)],
        capture_output=True,
        check=True,
    )
    return {p.name: p.read_text(encoding="utf-8") for p in target.iterdir()}


def read_vfat(path: Path) -> dict[str, str]:
    names = subprocess.run(
        ["mdir", "-i", str(path), "-b", "::/"], capture_output=True, text=True, check=True
    ).stdout.split()
    result = {}
    for name in names:
        name = name.removeprefix("::/")
        result[name] = subprocess.run(
            ["mtype", "-i", str(path), f"::/{name}"], capture_output=True, check=True
        ).stdout.decode("utf-8")
    return result


def write(tmp_path: Path, content: bytes, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


@pytest.fixture(autouse=True)
def isolated_tempdir(tmp_path: Path, monkeypatch) -> Path:
    """Route the builder's temporary files into a test directory to check cleanup."""
    temp = tmp_path / "tmp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    return temp


EXPECTED_FILES = {k: v for k, v in FILES.items() if v is not None}

pytest_anyio = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest_anyio
async def test_iso_has_cidata_label_and_files(tmp_path):
    """FR-002: the ISO is ISO 9660 with label cidata and the NoCloud files in its root."""
    image = write(tmp_path, await build_image(FILES, ImageFormat.ISO), "seed.iso")
    info = blkid(image)
    assert info["TYPE"] == "iso9660"
    assert info["LABEL"] == "cidata"
    assert read_iso(image, tmp_path / "extracted") == EXPECTED_FILES


@pytest_anyio
async def test_iso_has_joliet_and_rock_ridge():
    """FR-002: the ISO carries Joliet and Rock Ridge extensions (exact, lowercase file names)."""
    data = await build_image(FILES, ImageFormat.ISO)
    descriptors = [data[sector * 2048 : (sector + 1) * 2048] for sector in range(16, 20)]
    # Joliet: a supplementary volume descriptor (type 2) with a UCS-2 escape sequence.
    assert any(d[0] == 2 and d[1:6] == b"CD001" and d[88:91] == b"%/E" for d in descriptors)
    # Rock Ridge: NM entries keep the original name (plain ISO 9660 would store USER_DAT).
    assert b"NM" in data and b"user-data" in data


@pytest_anyio
async def test_raw_is_vfat_with_cidata_label_and_files(tmp_path):
    """FR-002: the RAW image has a VFAT filesystem labelled CIDATA with the NoCloud files."""
    image = write(tmp_path, await build_image(FILES, ImageFormat.RAW), "seed.img")
    info = blkid(image)
    assert info["TYPE"] == "vfat"
    assert info["LABEL"].lower() == "cidata"
    assert read_vfat(image) == EXPECTED_FILES


@pytest_anyio
async def test_qcow2_contains_the_raw_image(tmp_path):
    """FR-002: the QCOW2 image is the RAW image converted to QCOW2."""
    image = write(tmp_path, await build_image(FILES, ImageFormat.QCOW2), "seed.qcow2")
    info = json.loads(
        subprocess.run(
            ["qemu-img", "info", "--output", "json", str(image)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    assert info["format"] == "qcow2"
    raw = tmp_path / "converted.img"
    subprocess.run(
        ["qemu-img", "convert", "-f", "qcow2", "-O", "raw", str(image), str(raw)], check=True
    )
    assert blkid(raw)["LABEL"].lower() == "cidata"
    assert read_vfat(raw) == EXPECTED_FILES


@pytest_anyio
async def test_optional_files_are_included_when_present(tmp_path):
    """FR-001: network-config is part of the image when it has content."""
    files = {**FILES, "network-config": "version: 2\n"}
    image = write(tmp_path, await build_image(files, ImageFormat.RAW), "seed.img")
    assert read_vfat(image)["network-config"] == "version: 2\n"


@pytest_anyio
async def test_large_content_fits(tmp_path):
    """FR-002: the VFAT image grows with the content."""
    files = {**FILES, "user-data": "#cloud-config\n# " + "x" * 3_000_000 + "\n"}
    image = write(tmp_path, await build_image(files, ImageFormat.RAW), "seed.img")
    assert read_vfat(image)["user-data"] == files["user-data"]


@pytest_anyio
@pytest.mark.parametrize("image_format", list(ImageFormat))
async def test_temporary_files_are_removed(image_format, isolated_tempdir):
    """FR-003, NFR-005: no temporary files remain after generation."""
    await build_image(FILES, image_format)
    assert list(isolated_tempdir.iterdir()) == []


@pytest_anyio
async def test_temporary_files_are_removed_on_failure(isolated_tempdir, monkeypatch):
    """FR-003: temporary files are removed even if a tool fails."""
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(ImageBuildError):
        await build_image(FILES, ImageFormat.ISO)
    assert list(isolated_tempdir.iterdir()) == []


@pytest.mark.parametrize(
    ("name", "image_format", "expected"),
    [
        ("Web Server", ImageFormat.ISO, "web-server-cidata.iso"),
        ("db_01 (copy)", ImageFormat.RAW, "db-01-copy-cidata.img"),
        ("ÄÖÜ", ImageFormat.QCOW2, "seed-cidata.qcow2"),
        ("x" * 100, ImageFormat.ISO, "x" * 60 + "-cidata.iso"),
    ],
)
def test_file_name(name, image_format, expected):
    """FR-003: meaningful file name with matching extension."""
    assert image_file_name(name, image_format) == expected


# --- REST API ---


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(tinydb_path=tmp_path / "db.json"))) as client:
        yield client


@pytest.fixture
def configuration(client) -> dict:
    body = {"name": "Web Server", "basics": {"hostname": "web-01", "timezone": "UTC"}}
    return client.post("/api/configurations", json=body).json()


@pytest.mark.parametrize(
    ("image_format", "extension", "fs_type"),
    [("iso", ".iso", "iso9660"), ("raw", ".img", "vfat"), ("qcow2", ".qcow2", None)],
)
def test_download_image(client, configuration, tmp_path, image_format, extension, fs_type):
    """FR-003: the download has a meaningful file name and the matching extension."""
    response = client.get(
        f"/api/configurations/{configuration['id']}/image", params={"format": image_format}
    )
    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        f'attachment; filename="web-server-cidata{extension}"'
    )
    assert response.headers["cache-control"] == "no-store"
    image = write(tmp_path, response.content, f"download{extension}")
    if fs_type:
        assert blkid(image)["TYPE"] == fs_type


def test_download_contains_exactly_the_rendered_files(client, configuration, tmp_path):
    """FR-013: the image contains exactly the YAML returned by the files endpoint."""
    rendered = client.get(f"/api/configurations/{configuration['id']}/files").json()
    response = client.get(f"/api/configurations/{configuration['id']}/image?format=raw")
    image = write(tmp_path, response.content, "seed.img")
    assert read_vfat(image) == {k: v for k, v in rendered.items() if v is not None}


def test_download_defaults_to_iso(client, configuration):
    """FR-003: without a format, an ISO is delivered."""
    response = client.get(f"/api/configurations/{configuration['id']}/image")
    assert response.headers["content-disposition"].endswith('.iso"')


def test_download_generates_fresh_and_cleans_up(client, configuration, isolated_tempdir):
    """FR-003: the image is generated within the request; no files remain afterwards."""
    for image_format in ("iso", "raw", "qcow2"):
        url = f"/api/configurations/{configuration['id']}/image?format={image_format}"
        assert client.get(url).status_code == 200
    assert list(isolated_tempdir.iterdir()) == []


def test_download_unknown_configuration_returns_404(client):
    """FR-003: unknown configurations return HTTP 404."""
    response = client.get("/api/configurations/00000000-0000-4000-8000-000000000000/image")
    assert response.status_code == 404


def test_download_invalid_format_returns_422(client, configuration):
    """FR-003: only iso, raw and qcow2 are offered."""
    response = client.get(f"/api/configurations/{configuration['id']}/image?format=vmdk")
    assert response.status_code == 422


def test_download_failure_returns_500_without_details(client, configuration, monkeypatch):
    """FR-003: a failing tool results in HTTP 500 with a generic message."""
    monkeypatch.setenv("PATH", "/nonexistent")
    response = client.get(f"/api/configurations/{configuration['id']}/image")
    assert response.status_code == 500
    assert response.json() == {"detail": "Image generation failed."}
