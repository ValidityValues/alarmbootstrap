"""Pixel 4 helpers that reuse the existing Nura/postmarketOS kernel stack."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .rootfs import root_command

DEVICE_ID = "google-flame"
KERNEL_PACKAGE = "linux-postmarketos-qcom-sm8150"
DTB_RELATIVE = Path("boot/dtbs/qcom/sm8150-google-flame.dtb")


class Pixel4Error(RuntimeError):
    """A Pixel 4 staging or validation failure."""


def unpack_nura_packages(packages: list[Path], destination: Path) -> Path:
    """Extract selected APKs built with Nura into a temporary donor tree."""
    if not packages:
        raise Pixel4Error("Provide at least one --package (kernel and firmware APKs are needed).")
    if not shutil.which("bsdtar"):
        raise Pixel4Error("bsdtar is required to extract .apk packages (install libarchive).")

    destination = destination.expanduser().resolve()
    if destination.is_symlink():
        raise Pixel4Error(f"Refusing to extract into a symlink: {destination}")
    if destination.exists():
        raise Pixel4Error(
            f"Package staging directory already exists: {destination}. "
            "Remove it after inspecting its contents, then retry."
        )
    destination.mkdir(parents=True)

    for package_arg in packages:
        package = package_arg.expanduser().resolve()
        if not package.is_file() or package.suffix != ".apk":
            raise Pixel4Error(f"Expected an existing .apk file, got: {package}")
        listing = subprocess.run(
            ["bsdtar", "-tf", str(package)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout
        for member in listing.splitlines():
            path = Path(member)
            if path.is_absolute() or ".." in path.parts:
                raise Pixel4Error(f"Unsafe path in package {package.name}: {member!r}")
        subprocess.run(
            root_command(["bsdtar", "-xpf", str(package), "-C", str(destination)]),
            check=True,
        )
    return destination


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
        (source / "boot/linux.efi", target / "boot/linux-nura-sm8150.efi"),
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
        "Nura EFI reference kernel": (rootfs / "boot/linux-nura-sm8150.efi").is_file(),
        "Pixel 4 DTB": (rootfs / DTB_RELATIVE).is_file(),
    }
    modules = [
        path.name for path in (rootfs / "lib/modules").glob("*sm8150*")
        if path.is_dir() and (path / "modules.dep").is_file()
    ] if (rootfs / "lib/modules").is_dir() else []
    checks["SM8150 kernel modules"] = len(modules) == 1
    checks["firmware directory"] = (rootfs / "lib/firmware").is_dir()
    artifact_checks = {key: value for key, value in checks.items()}
    artifact_staging_complete = all(artifact_checks.values())
    return {
        "rootfs": str(rootfs),
        "checks": checks,
        "module_releases": modules,
        "artifact_staging_complete": artifact_staging_complete,
        "boot_path_complete": False,
        "boot_path_blockers": [
            "An Arch-compatible initramfs/UKI has not been generated.",
            "No verified root partition image or root identifier has been configured.",
            "The copied Nura EFI file is retained for inspection, not treated as an Arch boot image.",
        ],
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
