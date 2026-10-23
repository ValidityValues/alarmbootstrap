"""Safe chroot execution for staged Arch Linux ARM root filesystems."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from .rootfs import RootfsError, root_command


def _require_aarch64_execution() -> None:
    if platform.machine().lower() in {"aarch64", "arm64"}:
        return
    handler = Path("/proc/sys/fs/binfmt_misc/qemu-aarch64")
    if not handler.is_file():
        raise RootfsError(
            "Cross-architecture chroot requires a registered qemu-aarch64 binfmt handler. "
            "Configure host QEMU/binfmt first; alarmbootstrap will not modify host binfmt."
        )
    status = handler.read_text(encoding="utf-8", errors="replace")
    if "enabled" not in status.splitlines()[0].lower():
        raise RootfsError("The qemu-aarch64 binfmt handler exists but is not enabled.")


def run_in_rootfs(rootfs: Path, requested: list[str] | None = None) -> int:
    """Run a command with essential mounts and temporary host DNS inside the rootfs."""
    rootfs = rootfs.expanduser().resolve()
    if not (rootfs / "usr/bin/pacman").is_file() or not (rootfs / "bin/bash").exists():
        raise RootfsError(f"Not an Arch Linux ARM rootfs: {rootfs}")
    _require_aarch64_execution()

    command = list(requested or ["/bin/bash"])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        command = ["/bin/bash"]

    resolver_source = Path("/etc/resolv.conf")
    if not resolver_source.exists():
        raise RootfsError("Host /etc/resolv.conf is not available for chroot networking.")

    target_resolver = rootfs / "etc/resolv.conf"
    original_was_symlink = target_resolver.is_symlink()
    original_link = os.readlink(target_resolver) if original_was_symlink else None
    original_existed = target_resolver.exists() or original_was_symlink

    if original_was_symlink:
        subprocess.run(root_command(["rm", "-f", str(target_resolver)]), check=True)
    if not target_resolver.exists():
        subprocess.run(root_command(["touch", str(target_resolver)]), check=True)

    mounts: list[Path] = []
    try:
        for source in ("/dev", "/proc", "/sys"):
            target = rootfs / source.lstrip("/")
            subprocess.run(root_command(["mkdir", "-p", str(target)]), check=True)
            subprocess.run(root_command(["mount", "--rbind", source, str(target)]), check=True)
            mounts.append(target)

        subprocess.run(
            root_command(["mount", "--bind", str(resolver_source), str(target_resolver)]),
            check=True,
        )
        mounts.append(target_resolver)
        return subprocess.run(
            root_command(["chroot", str(rootfs), *command]), check=False
        ).returncode
    finally:
        for target in reversed(mounts):
            subprocess.run(root_command(["umount", "-R", str(target)]), check=False)
        if original_was_symlink:
            subprocess.run(root_command(["rm", "-f", str(target_resolver)]), check=False)
            subprocess.run(
                root_command(["ln", "-s", str(original_link), str(target_resolver)]),
                check=False,
            )
        elif not original_existed:
            subprocess.run(root_command(["rm", "-f", str(target_resolver)]), check=False)
