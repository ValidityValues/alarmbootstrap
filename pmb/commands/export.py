# Copyright 2026 Stefan Hansson, Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import fnmatch
import os
from pathlib import Path

import pmb.chroot.initfs
import pmb.helpers.run
from pmb.core import Chroot, ChrootType
from pmb.core.context import get_context
from pmb.helpers import logging


def odin(device: str, folder: Path) -> None:
    """
    Create Odin flashable tar file with kernel and initramfs
    for devices configured with the flasher method 'heimdall-isorec'
    and with boot.img for devices with 'heimdall-bootimg'
    """
    pmb.flasher.init(device, "heimdall-isorec")
    suffix = Chroot(ChrootType.ROOTFS, device)
    deviceinfo = pmb.parse.deviceinfo(device)

    # Validate method
    method = deviceinfo.flash_method or ""
    if not method.startswith("heimdall-"):
        raise RuntimeError(
            "An odin flashable tar is not supported"
            f" for the flash method '{method}' specified"
            " in the current configuration."
            " Only 'heimdall' methods are supported."
        )

    # Partitions
    partition_kernel = deviceinfo.flash_heimdall_partition_kernel or "KERNEL"
    partition_initfs = deviceinfo.flash_heimdall_partition_initfs or "RECOVERY"

    # Temporary folder
    temp_folder = "/tmp/odin-flashable-tar"
    if (Chroot.native() / temp_folder).exists():
        pmb.chroot.root(["rm", "-rf", temp_folder])

    # Odin flashable tar generation script
    # (because redirecting stdin/stdout is not allowed
    # in pmbootstrap's chroot/shell functions for security reasons)
    odin_script = Chroot(ChrootType.ROOTFS, device) / "tmp/_odin.sh"
    with odin_script.open("w") as handle:
        odin_kernel_md5 = f"{partition_kernel}.bin.md5"
        odin_initfs_md5 = f"{partition_initfs}.bin.md5"
        odin_device_tar = f"{device}.tar"
        odin_device_tar_md5 = f"{device}.tar.md5"

        handle.write(f"#!/bin/sh\ncd {temp_folder}\n")
        if method == "heimdall-isorec":
            handle.write(
                # Kernel: copy and append md5
                f"cp /boot/vmlinuz {odin_kernel_md5}\n"
                f"md5sum -t {odin_kernel_md5} >> {odin_kernel_md5}\n"
                # Initramfs: recompress with lzop, append md5
                f"gunzip -c /boot/initramfs"
                f" | lzop > {odin_initfs_md5}\n"
                f"md5sum -t {odin_initfs_md5} >> {odin_initfs_md5}\n"
            )
        elif method == "heimdall-bootimg":
            handle.write(
                # boot.img: copy and append md5
                f"cp /boot/boot.img {odin_kernel_md5}\n"
                f"md5sum -t {odin_kernel_md5} >> {odin_kernel_md5}\n"
            )
        handle.write(
            # Create tar, remove included files and append md5
            f"tar -c -f {odin_device_tar} *.bin.md5\n"
            "rm *.bin.md5\n"
            f"md5sum -t {odin_device_tar} >> {odin_device_tar}\n"
            f"mv {odin_device_tar} {odin_device_tar_md5}\n"
        )

    commands = [
        ["mkdir", "-p", temp_folder],
        ["cat", "/tmp/_odin.sh"],  # for the log
        ["sh", "/tmp/_odin.sh"],
        ["rm", "/tmp/_odin.sh"],
    ]
    for command in commands:
        pmb.chroot.root(command, suffix)

    # Move Odin flashable tar to native chroot and cleanup temp folder
    pmb.chroot.user(["mkdir", "-p", "/home/pmos/rootfs"])
    (
        pmb.chroot.root(
            [
                "mv",
                f"/mnt/rootfs_{device}{temp_folder}/{odin_device_tar_md5}",
                "/home/pmos/rootfs/",
            ]
        ),
    )
    pmb.chroot.root(["chown", "pmos:pmos", f"/home/pmos/rootfs/{odin_device_tar_md5}"])
    pmb.chroot.root(["rmdir", temp_folder], suffix)

    # Create the symlink
    file = Chroot.native() / "home/pmos/rootfs" / odin_device_tar_md5
    link = folder / odin_device_tar_md5
    pmb.helpers.file.symlink(file, link)

    # Display a readable message
    msg = f" * {odin_device_tar_md5}"
    if method == "heimdall-isorec":
        msg += " (Odin flashable file, contains initramfs and kernel)"
    elif method == "heimdall-bootimg":
        msg += " (Odin flashable file, contains boot.img)"
    logging.info(msg)


def symlinks(target: Path) -> None:
    """Create convenience symlinks to the rootfs and boot files."""
    device = get_context().config.device
    arch = pmb.parse.deviceinfo(device).arch

    # File descriptions
    info = {
        "boot.img": (
            "Fastboot compatible boot.img file, contains initramfs with bootimg header <=2 and kernel"
        ),
        "vendor_boot.img": (
            "Fastboot compatible vendor_boot.img file, contains cmdline, initramfs and dtb. Only with bootimg header >= v3"
        ),
        "dtbo.img": "Fastboot compatible dtbo image",
        "initramfs": "Initramfs",
        "initramfs-extra": "Extra initramfs files in /boot",
        "uInitrd": "Initramfs, legacy u-boot image format",
        "uImage": "Kernel, legacy u-boot image format",
        "vmlinuz": "Linux kernel",
        f"{device}.img": "Rootfs with subpartitions for /boot and /",
        f"{device}-boot.img": "Boot partition image (used in split installation)",
        f"{device}-root.img": "Root partition image (used in split installation)",
        f"pmos-{device}.zip": "Android recovery flashable zip",
        "lk2nd.img": "Secondary Android bootloader",
        "*.itb": "uBoot FIT image",
    }

    # Generate a list of patterns
    chroot_native = Chroot.native()
    path_boot = Chroot(ChrootType.ROOTFS, device) / "boot"
    chroot_buildroot = Chroot.buildroot(arch)
    files: list[Path] = [
        path_boot / "boot.img",
        path_boot / "vendor_boot.img",
        path_boot / "uInitrd",
        path_boot / "uImage",
        path_boot / "dtbo.img",
        chroot_native / "home/pmos/rootfs" / f"{device}.img",
        chroot_native / "home/pmos/rootfs" / f"{device}-boot.img",
        chroot_native / "home/pmos/rootfs" / f"{device}-root.img",
        chroot_buildroot / "var/lib/postmarketos-android-recovery-installer" / f"pmos-{device}.zip",
        path_boot / "lk2nd.img",
    ]

    files += list(path_boot.glob("initramfs*"))
    files += list(path_boot.glob("vmlinuz*"))
    files += list(path_boot.glob("*.itb"))

    # Iterate through all files
    for file in files:
        basename = file.name
        link = target / basename

        # Display a message and create a symlink only if target file actually exists
        if file.exists() and file.is_file():
            msg = " * " + basename
            if basename in info:
                msg += " (" + info[basename] + ")"
            else:
                for info_item in info:
                    if fnmatch.fnmatch(basename, info_item):
                        msg += " (" + info[info_item] + ")"
            logging.info(msg)

            pmb.helpers.file.symlink(file, link)

    # Create dtbs in folder
    dtbs = list(path_boot.glob("*.dtb"))
    if len(dtbs) == 0:
        return

    logging.info(" * dtbs/ (Device tree blobs)")
    target = target / "dtbs"
    target.mkdir(exist_ok=True)
    for dtb in dtbs:
        pmb.helpers.file.symlink(dtb, target / dtb.name)


def export(target: Path, autoinstall: bool, odin_flashable_tar: bool) -> None:
    config = get_context().config
    # Create the export folder
    if not os.path.exists(target):
        pmb.helpers.run.user(["mkdir", "-p", target])

    # Rootfs image note
    chroot = Chroot.native()
    rootfs_dir = chroot / "home/pmos/rootfs"
    if not any(rootfs_dir.glob(f"{config.device}*.img")):
        logging.info(
            "NOTE: To export the rootfs image, run 'pmbootstrap"
            " install' first (without the 'disk' parameter)."
        )

    # Rebuild the initramfs, just to make sure (see #69)
    if autoinstall:
        pmb.chroot.initfs.build(Chroot(ChrootType.ROOTFS, config.device))

    # Do the export, print all files
    logging.info(f"Export symlinks to: {target}")
    if odin_flashable_tar:
        odin(config.device, target)
    symlinks(target)
