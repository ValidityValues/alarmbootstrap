"""Download and safely stage the official generic Arch Linux ARM rootfs."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

DEFAULT_AARCH64_URL = "https://os.archlinuxarm.org/os/ArchLinuxARM-aarch64-latest.tar.gz"
MIN_FREE_BYTES = 3 * 1024**3


class RootfsError(RuntimeError):
    """An expected rootfs preparation failure."""


def root_command(command: list[str]) -> list[str]:
    """Prefix with sudo only if the current process is not root."""
    if os.geteuid() == 0:
        return command
    if shutil.which("sudo") is None:
        raise RootfsError("This operation needs root privileges; install sudo or run as root.")
    return ["sudo", *command]


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "alarmbootstrap/0.1.0 rootfs-downloader"}
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=destination.name + ".", suffix=".part", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "wb") as target, urllib.request.urlopen(request, timeout=60) as response:
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _download_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "alarmbootstrap/0.1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(64 * 1024).decode("utf-8", errors="replace")


def _published_md5(url: str) -> str:
    try:
        checksum_text = _download_text(url + ".md5")
    except Exception as exc:
        raise RootfsError(f"Could not download published checksum {url}.md5: {exc}") from exc
    match = re.search(r"\b([0-9a-fA-F]{32})\b", checksum_text)
    if not match:
        raise RootfsError(f"Unexpected MD5 checksum format from {url}.md5")
    return match.group(1).lower()


def _validate_archive(archive: Path) -> None:
    if shutil.which("bsdtar") is None:
        raise RootfsError(
            "bsdtar is required to preserve rootfs metadata (install libarchive/bsdtar)."
        )
    result = subprocess.run(
        ["bsdtar", "-tf", str(archive)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for member in result.stdout.splitlines():
        path = PurePosixPath(member)
        if path.is_absolute() or ".." in path.parts:
            raise RootfsError(f"Unsafe path in rootfs archive: {member!r}")


def install_rootfs(workdir: Path, url: str = DEFAULT_AARCH64_URL, force: bool = False) -> Path:
    """Download, checksum and extract an AArch64 rootfs; never flashes a device."""
    workdir = workdir.expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    destination = workdir / "rootfs"
    if destination.is_symlink():
        raise RootfsError(f"Refusing to use a symlink as the rootfs destination: {destination}")
    if destination.exists() and not force:
        raise RootfsError(
            f"Rootfs already exists: {destination}. Use --force to replace this directory."
        )
    if shutil.disk_usage(workdir).free < MIN_FREE_BYTES:
        raise RootfsError("At least 3 GiB free space is required before downloading the rootfs.")

    archive_name = Path(url.split("?", 1)[0]).name or "ArchLinuxARM-aarch64-latest.tar.gz"
    cache = workdir / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / archive_name
    source_marker = archive.with_suffix(archive.suffix + ".url")
    if (
        not archive.is_file()
        or not source_marker.is_file()
        or source_marker.read_text(encoding="utf-8").strip() != url
    ):
        _download(url, archive)
        source_marker.write_text(url + "\n", encoding="utf-8")

    expected = _published_md5(url)
    actual = hashlib.md5()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            actual.update(chunk)
    if actual.hexdigest().lower() != expected:
        archive.unlink(missing_ok=True)
        raise RootfsError(
            "Rootfs checksum differs from the publisher's MD5 file. Archive removed; retry."
        )

    _validate_archive(archive)
    if destination.exists():
        subprocess.run(root_command(["rm", "-rf", "--", str(destination)]), check=True)
    destination.mkdir(parents=True)
    try:
        subprocess.run(
            root_command(["bsdtar", "-xpf", str(archive), "-C", str(destination)]),
            check=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        subprocess.run(root_command(["rm", "-rf", "--", str(destination)]), check=False)
        raise RootfsError(f"Rootfs extraction failed: {exc}") from exc

    if not (destination / "usr/bin/pacman").is_file() or not (
        destination / "etc/os-release"
    ).is_file():
        raise RootfsError("Extracted archive does not look like an Arch Linux ARM rootfs.")
    return destination
