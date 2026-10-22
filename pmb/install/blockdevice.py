# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path

import pmb.config
import pmb.helpers.cli
import pmb.helpers.mount
import pmb.install.losetup
from pmb.core import Chroot
from pmb.core.context import get_context
from pmb.helpers import logging


def previous_install(path: Path) -> bool:
    """
    Search the disk for possible existence of a previous installation of
    pmOS. We temporarily mount the possible pmOS_boot partition as
    /dev/diskp1 inside the native chroot to check the label from there.

    :param path: path to disk block device (e.g. /dev/mmcblk0)
    """
    label = ""
    for blockdevice_outside in [path.with_stem(f"{path.name}1"), path.with_stem(f"{path.name}p1")]:
        if not blockdevice_outside.exists():
            continue
        blockdevice_inside = "/dev/diskp1"
        pmb.helpers.mount.bind_file(blockdevice_outside, Chroot.native() / blockdevice_inside)
        try:
            label = pmb.chroot.root(
                ["blkid", "-s", "LABEL", "-o", "value", blockdevice_inside], output_return=True
            )
        except RuntimeError:
            logging.info(
                "WARNING: Could not get block device label,"
                " assume no previous installation on that partition"
            )

        pmb.helpers.run.root(["umount", Chroot.native() / blockdevice_inside])
    return "pmOS_boot" in label


def mount_disk(path: Path) -> None:
    """:param path: path to disk block device (e.g. /dev/mmcblk0)"""
    # Sanity checks
    if not path.exists():
        raise RuntimeError(f"The disk block device does not exist: {path}")
    for path_mount in path.parent.glob(f"{path.name}*"):
        if pmb.helpers.mount.ismount(path_mount):
            raise RuntimeError(f"{path_mount} is mounted! Will not attempt to format this!")
    logging.info(f"(native) mount /dev/install (host: {path})")
    pmb.helpers.mount.bind_file(path, Chroot.native() / "dev/install")
    if previous_install(path):
        if not pmb.helpers.cli.confirm(
            "WARNING: This device has a previous installation of pmOS. CONTINUE?"
        ):
            raise RuntimeError("Aborted.")
    else:
        if not pmb.helpers.cli.confirm(f"EVERYTHING ON {path} WILL BE ERASED! CONTINUE?"):
            raise RuntimeError("Aborted.")


def create_and_mount_image(
    sector_size: int | None, size_boot: int, size_root: int, split: bool = False
) -> None:
    """
    Create a new image file, and mount it as /dev/install.

    :param size_boot: size of the boot partition in MiB
    :param size_root: size of the root partition in MiB
    :param split: create separate images for boot and root partitions
    """
    # Short variables for paths
    chroot = Chroot.native()
    config = get_context().config
    img_path_prefix = Path("/home/pmos/rootfs")
    img_path_full = img_path_prefix / f"{config.device}.img"
    img_path_boot = img_path_prefix / f"{config.device}-boot.img"
    img_path_root = img_path_prefix / f"{config.device}-root.img"

    # Umount and delete existing images
    for img_path in [img_path_full, img_path_boot, img_path_root]:
        outside = chroot / img_path
        if outside.exists():
            pmb.helpers.mount.umount_all(chroot / "mnt")
            pmb.install.losetup.umount(img_path)
            pmb.chroot.root(["rm", img_path])

    # Make sure there is enough free space
    size_mb = round(size_boot + size_root)
    disk_data = os.statvfs(get_context().config.work)
    free = round((disk_data.f_bsize * disk_data.f_bavail) / (1024**2))
    if size_mb > free:
        raise RuntimeError(
            f"Not enough free space to create rootfs image! (free: {free}M, required: {size_mb}M)"
        )

    # Create empty image files
    pmb.chroot.user(["mkdir", "-p", "/home/pmos/rootfs"])
    size_mb_full = str(size_mb) + "M"
    size_mb_boot = str(size_boot) + "M"
    size_mb_root = str(size_root) + "M"
    images = {img_path_full: size_mb_full}
    if split:
        images = {img_path_boot: size_mb_boot, img_path_root: size_mb_root}
    for img_path, image_size_mb in images.items():
        logging.info(f"(native) create {img_path.name} ({image_size_mb})")
        pmb.chroot.root(["truncate", "-s", image_size_mb, img_path])

    # Mount to /dev/install
    mount_image_paths = {img_path_full: "/dev/install"}
    if split:
        mount_image_paths = {img_path_boot: "/dev/installp1", img_path_root: "/dev/installp2"}

    for img_path, mount_point in mount_image_paths.items():
        logging.info(f"(native) mount {mount_point} ({img_path.name})")
        pmb.install.losetup.mount(img_path, sector_size)
        device = pmb.install.losetup.device_by_back_file(img_path)
        pmb.helpers.mount.bind_file(device, Chroot.native() / mount_point)


def create(sector_size: int | None, size_boot: int, size_root: int, split: bool) -> None:
    """
    Create /dev/install (the "install blockdevice").

    :param size_boot: size of the boot partition in MiB
    :param size_root: size of the root partition in MiB
    :param split: create separate images for boot and root partitions
    """
    pmb.helpers.mount.umount_all(Chroot.native() / "dev/install")
    create_and_mount_image(sector_size, size_boot, size_root, split)


def handle_disk_mount(disk: Path) -> None:
    """
    Mount disk as /dev/install (the "install blockdevice").

    :param disk: path to disk block device (e.g. /dev/mmcblk0).
    """
    pmb.helpers.mount.umount_all(Chroot.native() / "dev/install")
    mount_disk(disk)
