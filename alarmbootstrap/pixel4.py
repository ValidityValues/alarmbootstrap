"""Pixel 4 helpers that reuse the existing Nura/postmarketOS kernel stack."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .chroot import run_in_rootfs
from .rootfs import RootfsError, root_command

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
    uki = rootfs / "boot/EFI/BOOT/BOOTAA64.EFI"
    initramfs = rootfs / "boot/initramfs-alarmbootstrap-sm8150.img"
    metadata = rootfs / "boot/alarmbootstrap-boot.json"
    efi_bundle_generated = uki.is_file() and initramfs.is_file() and metadata.is_file()
    artifact_staging_complete = all(checks.values())
    blockers = []
    if not efi_bundle_generated:
        blockers.append("Run alarmbootstrap pixel4 build-efi to generate an Arch-compatible initramfs/UKI.")
    blockers.append("A generated UKI is not a substitute for testing the complete image on the physical Pixel 4.")
    return {
        "rootfs": str(rootfs),
        "checks": checks,
        "module_releases": modules,
        "artifact_staging_complete": artifact_staging_complete,
        "efi_bundle_generated": efi_bundle_generated,
        "physical_boot_verified": False,
        "boot_path_blockers": blockers,
    }


def build_efi(rootfs: Path, root_label: str = "ALARMROOT") -> Path:
    """Generate an Arch-compatible initramfs and ARM64 UKI with the existing Nura kernel."""
    rootfs = rootfs.expanduser().resolve()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", root_label):
        raise Pixel4Error("Root label must use only letters, digits, dot, underscore or hyphen (max 32 chars).")
    if not (rootfs / "usr/bin/pacman").is_file():
        raise Pixel4Error(f"Arch Linux ARM rootfs not found: {rootfs}")
    kernel = rootfs / "boot/vmlinuz-postmarketos-sm8150"
    dtb = rootfs / DTB_RELATIVE
    if not kernel.is_file() or not dtb.is_file():
        raise Pixel4Error("Stage the existing Nura kernel and DTB before running pixel4 build-efi.")

    module_dirs = sorted(
        path for path in (rootfs / "lib/modules").glob("*sm8150*")
        if path.is_dir() and (path / "modules.dep").is_file()
    ) if (rootfs / "lib/modules").is_dir() else []
    if len(module_dirs) != 1:
        raise Pixel4Error("Expected exactly one staged SM8150 modules directory with modules.dep.")
    kernel_release = module_dirs[0].name
    if not re.fullmatch(r"[A-Za-z0-9._+-]{1,128}", kernel_release):
        raise Pixel4Error(f"Unexpected kernel release directory name: {kernel_release!r}")

    script = r"""set -Eeuo pipefail
kernel_release="$1"
root_label="$2"

# Initialize the generic Arch Linux ARM keyring using the official instructions,
# then update userspace and install the tools used to build an initramfs/UKI.
pacman-key --init
pacman -Sy --noconfirm archlinuxarm-keyring
pacman-key --populate archlinuxarm
pacman -Syu --noconfirm --needed mkinitcpio systemd-ukify binutils

cat > /etc/mkinitcpio-alarmbootstrap.conf <<'EOF'
MODULES=(loop)
BINARIES=(/usr/bin/blkid /usr/bin/losetup /usr/bin/udevadm)
FILES=()
HOOKS=(base udev modconf block alarmbootstrap-nestedpart filesystems fsck)
COMPRESSION="zstd"
EOF

mkdir -p /etc/initcpio/hooks /etc/initcpio/install
cat > /etc/initcpio/install/alarmbootstrap-nestedpart <<'EOF'
#!/usr/bin/bash
build() {
    add_module loop
    add_binary /usr/bin/blkid
    add_binary /usr/bin/losetup
    add_binary /usr/bin/udevadm
    add_runscript
}
help() {
    cat <<'HELP'
Scan the Android userdata partition as a disk image to expose its nested GPT partitions.
HELP
}
EOF
cat > /etc/initcpio/hooks/alarmbootstrap-nestedpart <<'EOF'
run_hook() {
    local device label loopdev
    for device in /dev/sd* /dev/nvme* /dev/mmcblk*; do
        [[ -b "$device" ]] || continue
        label="$(blkid -s PARTLABEL -o value "$device" 2>/dev/null || true)"
        if [[ "$label" == "userdata" ]]; then
            msg "Found userdata partition at $device; scanning nested GPT"
            loopdev="$(losetup --find --show --partscan "$device")" || return 1
            udevadm settle
            msg "Nested partitions exposed through $loopdev"
            return 0
        fi
    done
    err "Could not find Android userdata (PARTLABEL=userdata)"
    return 1
}
EOF
chmod 0644 /etc/mkinitcpio-alarmbootstrap.conf
mkinitcpio -c /etc/mkinitcpio-alarmbootstrap.conf \
    -k "$kernel_release" -g /boot/initramfs-alarmbootstrap-sm8150.img

mkdir -p /boot/EFI/BOOT
ukify build \
    --linux=/boot/vmlinuz-postmarketos-sm8150 \
    --initrd=/boot/initramfs-alarmbootstrap-sm8150.img \
    --cmdline="root=LABEL=$root_label rw rootwait rootfstype=ext4" \
    --os-release=@/etc/os-release \
    --devicetree=/boot/dtbs/qcom/sm8150-google-flame.dtb \
    --output=/boot/EFI/BOOT/BOOTAA64.EFI
"""
    status = run_in_rootfs(
        rootfs,
        ["/bin/bash", "-euc", script, "alarmbootstrap-build-efi", kernel_release, root_label],
    )
    if status:
        raise Pixel4Error(
            f"Building the Arch initramfs/UKI failed inside the rootfs (exit {status}). "
            "Inspect the chroot output and rootfs package/keyring configuration."
        )

    uki = rootfs / "boot/EFI/BOOT/BOOTAA64.EFI"
    initramfs = rootfs / "boot/initramfs-alarmbootstrap-sm8150.img"
    if not uki.is_file() or not initramfs.is_file():
        raise Pixel4Error("The UKI build returned success but did not produce the expected files.")

    metadata = {
        "device": DEVICE_ID,
        "kernel_release": kernel_release,
        "kernel": "/boot/vmlinuz-postmarketos-sm8150",
        "dtb": str(DTB_RELATIVE),
        "initramfs": "/boot/initramfs-alarmbootstrap-sm8150.img",
        "uki": "/boot/EFI/BOOT/BOOTAA64.EFI",
        "root_label": root_label,
        "root_filesystem": "ext4",
        "kernel_command_line": f"root=LABEL={root_label} rw rootwait rootfstype=ext4",
        "note": "Generated host-side; this does not prove boot on the physical device.",
    }
    data = json.dumps(metadata, indent=2) + "\n"
    subprocess.run(
        root_command(["tee", str(rootfs / "boot/alarmbootstrap-boot.json")]),
        input=data,
        text=True,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        root_command(["chmod", "0644", str(rootfs / "boot/alarmbootstrap-boot.json")]),
        check=True,
    )
    return uki


def build_disk_image(
    rootfs: Path,
    destination: Path,
    *,
    esp_mib: int = 512,
    force: bool = False,
) -> Path:
    """Create a nested GPT image with a FAT EFI partition and ext4 Arch root partition."""
    rootfs = rootfs.expanduser().resolve()
    destination = destination.expanduser()
    if destination.is_symlink():
        raise Pixel4Error(f"Refusing to replace a symlink: {destination}")
    destination = destination.resolve()
    if destination.exists() and not force:
        raise Pixel4Error(f"Image already exists: {destination}. Use --force to replace this image.")
    if destination == rootfs or rootfs in destination.parents:
        raise Pixel4Error("Image output must be outside the rootfs directory.")
    if not (rootfs / "usr/bin/pacman").is_file():
        raise Pixel4Error(f"Arch Linux ARM rootfs not found: {rootfs}")

    uki = rootfs / "boot/EFI/BOOT/BOOTAA64.EFI"
    metadata_path = rootfs / "boot/alarmbootstrap-boot.json"
    if not uki.is_file() or not metadata_path.is_file():
        raise Pixel4Error("Run alarmbootstrap pixel4 build-efi before building the disk image.")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    root_label = metadata.get("root_label")
    if not isinstance(root_label, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", root_label):
        raise Pixel4Error("Invalid root label in boot metadata.")

    for tool in ("sgdisk", "mkfs.fat", "mkfs.ext4", "losetup", "mount", "umount", "truncate"):
        if shutil.which(tool) is None:
            raise Pixel4Error(f"Missing image-building tool: {tool}")

    root_bytes = sum(
        path.stat().st_size
        for path in rootfs.rglob("*")
        if path.is_file() and not path.is_symlink()
    )
    root_mib = max(2048, math.ceil((root_bytes * 1.30 + 512 * 1024**2) / 1024**2))
    if esp_mib < 128 or esp_mib > 2048:
        raise Pixel4Error("EFI partition size must be between 128 and 2048 MiB.")
    total_mib = esp_mib + root_mib + 16
    destination.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination.parent).free < total_mib * 1024**2:
        raise Pixel4Error(
            f"Building this image needs about {total_mib} MiB free in {destination.parent}."
        )

    fd, temporary_name = tempfile.mkstemp(
        prefix=destination.name + ".", suffix=".tmp", dir=destination.parent
    )
    os.close(fd)
    temporary_image = Path(temporary_name)
    loop_device = ""
    mountpoint = ""
    mounted = False
    try:
        subprocess.run(["truncate", "-s", str(total_mib * 1024**2), str(temporary_image)], check=True)
        subprocess.run(
            [
                "sgdisk", "--clear",
                "--new=1:2048:+" + str(esp_mib) + "M",
                "--typecode=1:ef00", "--change-name=1:ALARMBOOT",
                "--new=2:0:0", "--typecode=2:8300", "--change-name=2:ALARMROOT",
                str(temporary_image),
            ],
            check=True,
        )
        attach = subprocess.run(
            root_command(["losetup", "--find", "--show", "--partscan", str(temporary_image)]),
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        loop_device = attach.stdout.strip()
        if not loop_device.startswith("/dev/loop"):
            raise Pixel4Error(f"Unexpected loop device returned by losetup: {loop_device!r}")
        if shutil.which("udevadm"):
            subprocess.run(root_command(["udevadm", "settle"]), check=False)

        efi_partition = loop_device + "p1"
        root_partition = loop_device + "p2"
        for _ in range(50):
            if Path(efi_partition).exists() and Path(root_partition).exists():
                break
            time.sleep(0.1)
        if not Path(efi_partition).exists() or not Path(root_partition).exists():
            raise Pixel4Error("Kernel did not expose the image's loop partition devices.")

        subprocess.run(root_command(["mkfs.fat", "-F", "32", "-n", "ALARMBOOT", efi_partition]), check=True)
        subprocess.run(
            root_command(["mkfs.ext4", "-F", "-L", root_label, "-d", str(rootfs), root_partition]),
            check=True,
        )

        with tempfile.TemporaryDirectory(prefix="alarmbootstrap-esp-") as temp_mount:
            mountpoint = temp_mount
            subprocess.run(root_command(["mount", efi_partition, mountpoint]), check=True)
            mounted = True
            try:
                efi_dir = Path(mountpoint) / "EFI" / "BOOT"
                subprocess.run(root_command(["mkdir", "-p", str(efi_dir)]), check=True)
                subprocess.run(
                    root_command(["cp", str(uki), str(efi_dir / "BOOTAA64.EFI")]), check=True
                )
                subprocess.run(["sync"], check=True)
            finally:
                if mounted:
                    subprocess.run(root_command(["umount", mountpoint]), check=True)
                    mounted = False
        subprocess.run(root_command(["losetup", "-d", loop_device]), check=True)
        loop_device = ""
        os.replace(temporary_image, destination)
        return destination
    except (OSError, subprocess.CalledProcessError) as exc:
        raise Pixel4Error(f"Creating the nested GPT image failed: {exc}") from exc
    finally:
        if mounted and mountpoint:
            subprocess.run(root_command(["umount", "-R", mountpoint]), check=False)
        if loop_device:
            subprocess.run(root_command(["losetup", "-d", loop_device]), check=False)
        temporary_image.unlink(missing_ok=True)


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
