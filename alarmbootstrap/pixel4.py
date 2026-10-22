"""Pixel 4 helpers that reuse the existing Nura/postmarketOS kernel stack."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .rootfs import root_command

DEVICE_ID = "google-flame"
KERNEL_PACKAGE = "linux-postmarketos-qcom-sm8150"
DTB_RELATIVE = Path("boot/dtbs/qcom/sm8150-google-flame.dtb")


class Pixel4Error(RuntimeError):
    """A Pixel 4 staging or validation failure."""


def stage_kernel(nura_rootfs: Path, arch_rootfs: Path) -> list[Path]:
    """Copy existing Nura kernel artifacts, modules and firmware into an ALARM rootfs."""
    source = nura_rootfs.expanduser().resolve()
    target = arch_rootfs.expanduser().resolve()
    if source == target:
        raise Pixel4Error("The Nura source rootfs and Arch destination rootfs must be different.")
    if not (target / "usr/bin/pacman").is_file():
        raise Pixel4Error(f"Destination is not an Arch Linux ARM rootfs: {target}")
    if not source.is_dir():
        raise Pixel4Error(f"Nura rootfs directory not found: {source}")

    required = [source / "boot/linux.efi", source / DTB_RELATIVE]
    missing = [path for path in required if not path.is_file()]
    if missing:
        names = ", ".join(str(path) for path in missing)
        raise Pixel4Error(
            f"Missing existing Pixel 4 kernel artifact(s): {names}. "
            f"Expected the {KERNEL_PACKAGE} package from Nura/postmarketOS."
        )

    modules_root = source / "lib/modules"
    module_dirs = sorted(
        path for path in modules_root.glob("*sm8150*")
        if path.is_dir() and (path / "modules.dep").is_file()
    ) if modules_root.is_dir() else []
    if len(module_dirs) != 1:
        raise Pixel4Error(
            f"Expected exactly one matching SM8150 module directory with modules.dep in "
            f"{modules_root}; found {len(module_dirs)}. Use a consistent Nura kernel rootfs."
        )

    source_firmware = source / "lib/firmware"
    if not source_firmware.exists():
        source_firmware = source / "usr/lib/firmware"
    if not source_firmware.is_dir():
        raise Pixel4Error(f"No firmware directory found in the Nura rootfs: {source}")

    copies: list[tuple[Path, Path]] = [
        (source / "boot/linux.efi", target / "boot/alarmbootstrap-sm8150.efi"),
        (source / DTB_RELATIVE, target / DTB_RELATIVE),
        (module_dirs[0], target / "lib/modules" / module_dirs[0].name),
    ]
    vmlinuz = source / "boot/vmlinuz"
    if vmlinuz.is_file():
        copies.append((vmlinuz, target / "boot/vmlinuz-postmarketos-sm8150"))

    for _src, dst in copies:
        subprocess.run(root_command(["mkdir", "-p", str(dst.parent)]), check=True)
    for src_path, dst_path in copies:
        subprocess.run(root_command(["cp", "-a", str(src_path), str(dst_path)]), check=True)

    firmware_target = target / "lib/firmware"
    subprocess.run(root_command(["mkdir", "-p", str(firmware_target)]), check=True)
    # Add missing firmware files only; do not overwrite the files from Arch.
    subprocess.run(
        root_command(["cp", "-an", str(source_firmware) + "/.", str(firmware_target) + "/"]),
        check=True,
    )

    staged = [destination for _source, destination in copies]
    staged.append(firmware_target)
    return staged


def inspect_rootfs(rootfs: Path) -> dict[str, object]:
    """Report staged files; this does not claim that the phone has booted."""
    rootfs = rootfs.expanduser().resolve()
    checks = {
        "Arch Linux ARM rootfs": (rootfs / "usr/bin/pacman").is_file(),
        "Nura SM8150 EFI kernel": (rootfs / "boot/alarmbootstrap-sm8150.efi").is_file(),
        "Pixel 4 DTB": (rootfs / DTB_RELATIVE).is_file(),
    }
    modules = [
        path.name for path in (rootfs / "lib/modules").glob("*sm8150*")
        if path.is_dir() and (path / "modules.dep").is_file()
    ] if (rootfs / "lib/modules").is_dir() else []
    checks["SM8150 kernel modules"] = len(modules) == 1
    checks["firmware directory"] = (rootfs / "lib/firmware").is_dir()
    return {
        "rootfs": str(rootfs),
        "checks": checks,
        "module_releases": modules,
        "ready_for_hardware_test": all(checks.values()),
    }


def run_uboot_build(
    flash: bool = False, source: Path | None = None, workdir: Path | None = None
) -> int:
    """Run the repository's U-Boot build script."""
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts/build-google-flame-uboot.sh"
    if not script.is_file():
        raise Pixel4Error(f"U-Boot build helper is missing: {script}")
    command = [str(script)]
    if source:
        command += ["--source", str(source.expanduser().resolve())]
    if workdir:
        command += ["--workdir", str(workdir.expanduser().resolve())]
    if flash:
        command.append("--flash")
    return subprocess.run(command, check=False).returncode
