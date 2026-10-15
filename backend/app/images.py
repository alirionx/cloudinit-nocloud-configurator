"""Seed image generation (FR-002) without root privileges or mounts (NFR-002).

Images are built in a temporary directory that exists only for the duration of
one request (FR-003, NFR-005):

- ISO:   ISO 9660 with Joliet and Rock Ridge, volume ID `cidata` (xorriso)
- RAW:   VFAT disk image, label `CIDATA` (mkfs.vfat + mtools)
- QCOW2: the RAW image converted with qemu-img
"""

import asyncio
import logging
import math
import os
import re
import shutil
import tempfile
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)

TOOLS = ("xorriso", "mkfs.vfat", "mcopy", "qemu-img")
TOOL_TIMEOUT_SECONDS = 30
# Limits concurrent builds so that a burst of downloads cannot exhaust CPU or /tmp.
_build_slots = asyncio.Semaphore(4)


class ImageFormat(StrEnum):
    ISO = "iso"
    RAW = "raw"
    QCOW2 = "qcow2"


EXTENSIONS = {ImageFormat.ISO: ".iso", ImageFormat.RAW: ".img", ImageFormat.QCOW2: ".qcow2"}
MEDIA_TYPES = {
    ImageFormat.ISO: "application/x-iso9660-image",
    ImageFormat.RAW: "application/octet-stream",
    ImageFormat.QCOW2: "application/octet-stream",
}


class ImageBuildError(Exception):
    """An image tool failed or timed out."""


def missing_tools() -> list[str]:
    return [tool for tool in TOOLS if shutil.which(tool) is None]


def image_file_name(name: str, image_format: ImageFormat) -> str:
    """FR-003: a meaningful, ASCII-safe file name, e.g. 'web-server-cidata.iso'."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60].strip("-") or "seed"
    return f"{slug}-cidata{EXTENSIONS[image_format]}"


async def build_image(files: dict[str, str | None], image_format: ImageFormat) -> bytes:
    """Build a seed image containing the given NoCloud files and return its content.

    Files with value `None` are omitted. All temporary files are removed before
    this function returns, also on errors (FR-003).
    """
    async with _build_slots:
        workdir = Path(tempfile.mkdtemp(prefix="cnc-seed-"))
        try:
            seed = workdir / "seed"
            seed.mkdir()
            for file_name, content in files.items():
                if content is not None:
                    (seed / file_name).write_text(content, encoding="utf-8")
            if image_format is ImageFormat.ISO:
                image = await _build_iso(seed, workdir)
            else:
                image = await _build_vfat(seed, workdir)
                if image_format is ImageFormat.QCOW2:
                    image = await _convert_to_qcow2(image, workdir)
            return image.read_bytes()
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


async def _build_iso(seed: Path, workdir: Path) -> Path:
    output = workdir / "seed.iso"
    await _run(
        "xorriso", "-as", "mkisofs", "-quiet", "-output", str(output),
        "-volid", "cidata", "-joliet", "-rock", "-input-charset", "utf-8", str(seed),
        cwd=workdir,
    )  # fmt: skip
    return output


def _vfat_size_bytes(seed: Path) -> int:
    """Content plus generous headroom for FAT metadata, in whole MiB (at least 2 MiB)."""
    content = sum(path.stat().st_size for path in seed.iterdir())
    mib = 1024 * 1024
    return max(2, math.ceil((content * 1.2 + mib) / mib)) * mib


async def _build_vfat(seed: Path, workdir: Path) -> Path:
    output = workdir / "seed.img"
    with output.open("wb") as handle:
        handle.truncate(_vfat_size_bytes(seed))
    # FAT labels are upper case; cloud-init accepts CIDATA as well as cidata.
    await _run("mkfs.vfat", "-n", "CIDATA", str(output), cwd=workdir)
    sources = [str(path) for path in sorted(seed.iterdir())]
    await _run("mcopy", "-i", str(output), "-o", *sources, "::/", cwd=workdir)
    return output


async def _convert_to_qcow2(raw: Path, workdir: Path) -> Path:
    output = workdir / "seed.qcow2"
    await _run(
        "qemu-img", "convert", "-f", "raw", "-O", "qcow2", str(raw), str(output), cwd=workdir
    )
    return output


async def _run(*command: str, cwd: Path) -> None:
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(cwd),
        "LANG": "C.UTF-8",
        "MTOOLS_SKIP_CHECK": "1",
    }
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ImageBuildError(f"{command[0]} is not installed") from exc
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), TOOL_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise ImageBuildError(f"{command[0]} timed out") from exc
    if process.returncode != 0:
        # stderr of these tools contains file names and sizes, never file content.
        message = stderr.decode(errors="replace").strip()[-500:]
        raise ImageBuildError(f"{command[0]} failed with exit code {process.returncode}: {message}")
