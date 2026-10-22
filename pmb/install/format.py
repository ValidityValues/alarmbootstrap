# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import tempfile

import pmb.chroot
from pmb.core import Chroot
from pmb.core.context import get_context
from pmb.helpers import logging
from pmb.helpers.devices import get_device_category_by_name
from pmb.types import PartitionLayout, PathString, RunOutputTypeDefault


def install_fsprogs(filesystem: str) -> None:
    """Install the package required to format a specific filesystem."""
    fsprogs = pmb.config.filesystems.get(filesystem)
    if not fsprogs:
        raise RuntimeError(f"Unsupported filesystem: {filesystem}")
    pmb.chroot.apk.install([fsprogs], Chroot.native())


def format_partition_with_filesystem(
    device: str, label: str, filesystem: str, is_disk: bool
) -> None:
    """
    :param device: partition to format with filesystem
    :param label: label to apply to filesystem
    :param filesystem: filesystem type to format partition with
    :param is_disk: whether we are formatting on physical disk
    """
    # Install binaries for formatting the selected filesystem
    install_fsprogs(filesystem)

    # Create formatting command
    if filesystem == "ext4":
        # ext4 uses more complex logic because it is used by downstream kernels
        device_category = get_device_category_by_name(get_context().config.device)
        if device_category.allows_downstream_ports():
            # Some downstream kernels don't support metadata_csum (#1364).
            # When changing the options of mkfs.ext4, also change them in the
            # recovery zip code (see 'grep -r mkfs\.ext4')!
            category_opts = ["-O", "^metadata_csum"]
        else:
            category_opts = []
        mkfs_args = ["mkfs.ext4", *category_opts, "-F", "-q", "-L", label]
        if not is_disk:
            # pmb#2568: tell mkfs.ext4 to make a filesystem with enough
            # indoes that we don't run into "out of space" errors
            mkfs_args = [*mkfs_args, "-i", "8192"]
    elif filesystem == "fat16":
        mkfs_args = ["mkfs.fat", "-F", "16", "-n", label]
    elif filesystem == "fat32":
        mkfs_args = ["mkfs.fat", "-F", "32", "-n", label]
    elif filesystem == "ext2":
        mkfs_args = ["mkfs.ext2", "-F", "-q", "-L", label]
    elif filesystem == "f2fs":
        mkfs_args = ["mkfs.f2fs", "-O extra_attr,inode_checksum,sb_checksum", "-f", "-l", label]
    elif filesystem == "btrfs":
        mkfs_args = ["mkfs.btrfs", "-f", "-q", "-L", label]
    elif filesystem == "xfs":
        # mkfs.xfs requires specifying the sector size
        mkfs_args = ["mkfs.xfs", "-f", "-q"]
        sector_size = pmb.parse.deviceinfo().rootfs_image_sector_size
        if sector_size is None or sector_size in {"", "512"}:
            mkfs_args += ["-s", "size=512"]
        else:
            mkfs_args += [
                "-b",
                "size=" + str(int(sector_size) * 2),
                "-s",
                "size=" + str(sector_size),
            ]
        mkfs_args += ["-L", label]
    else:
        raise RuntimeError("Filesystem " + filesystem + " is not supported!")

    # Format the partition with the selected filesystem
    logging.info(f"(native) format {device} ({label}, {filesystem})")
    pmb.chroot.root([*mkfs_args, device])


def format_and_mount_boot(device: str, boot_label: str) -> None:
    """
    :param device: boot partition on install block device (e.g. /dev/installp1)
    :param boot_label: label of the root partition (e.g. "pmOS_boot")
    """
    mountpoint = "/mnt/install/boot"
    filesystem = (
        pmb.parse.deviceinfo().boot_filesystem
        or pmb.parse.deviceinfo_schema_default_boot_filesystem()
    )
    format_partition_with_filesystem(device, boot_label, filesystem, False)

    pmb.chroot.root(["mkdir", "-p", mountpoint])
    pmb.chroot.root(["mount", device, mountpoint])


def format_luks_root(device: str, cipher: str, iter_time: str) -> None:
    """:param device: root partition on install block device (e.g. /dev/installp2)"""
    mountpoint = "/dev/mapper/pm_crypt"

    logging.info(f"(native) format {device} (root, luks), mount to {mountpoint}")
    logging.info(" *** TYPE IN THE FULL DISK ENCRYPTION PASSWORD (TWICE!) ***")

    # Avoid cryptsetup warning about missing locking directory
    pmb.chroot.root(["mkdir", "-p", "/run/cryptsetup"])

    format_cmd = [
        "cryptsetup",
        "luksFormat",
        "-q",
        "--cipher",
        cipher,
        "--iter-time",
        iter_time,
        "--use-random",
        device,
    ]
    open_cmd = ["cryptsetup", "luksOpen"]

    path_outside = None
    fde_key = os.environ.get("PMB_FDE_PASSWORD", None)
    if fde_key:
        # Write passphrase to a temp file, to avoid printing it in any log
        path = tempfile.mktemp(dir="/tmp")
        path_outside = Chroot.native() / path
        path_outside.write_text(fde_key, encoding="utf-8")
        format_cmd += [str(path)]
        open_cmd += ["--key-file", str(path)]

    try:
        pmb.chroot.root(format_cmd, output=RunOutputTypeDefault.INTERACTIVE)
        pmb.chroot.root([*open_cmd, device, "pm_crypt"], output=RunOutputTypeDefault.INTERACTIVE)
    finally:
        if path_outside:
            path_outside.unlink()

    if not (Chroot.native() / mountpoint).exists():
        raise RuntimeError("Failed to open cryptdevice!")


def get_root_filesystem(filesystem: str | None) -> str:
    ret = filesystem or pmb.parse.deviceinfo().root_filesystem or "ext4"
    pmaports_cfg = pmb.config.pmaports.read_config()

    supported = pmaports_cfg.get("supported_root_filesystems", "ext4")
    supported_list = supported.split(",")

    if ret not in supported_list:
        raise ValueError(
            f"Root filesystem {ret} is not supported by your"
            " currently checked out pmaports branch. Update your"
            " branch ('pmbootstrap pull'), change it"
            " ('pmbootstrap init'), or select one of these"
            f" filesystems: {', '.join(supported_list)}"
        )
    return ret


def prepare_btrfs_subvolumes(device: str, mountpoint: str) -> None:
    """
    Create separate subvolumes if root filesystem is btrfs.
    This lets us do snapshots and rollbacks of relevant parts
    of the filesystem.
    /var contains logs, VMs, containers, flatpaks; and shouldn't roll back,
    /root is root's home directory and shouldn't roll back,
    /tmp has temporary files, snapshotting them is unnecessary,
    /srv contains data for web and FTP servers, and shouldn't roll back,
    /snapshots should be a separate subvol so that changing the root subvol
    doesn't affect snapshots
    """
    subvolume_list = ["@", "@home", "@root", "@snapshots", "@srv", "@tmp", "@var"]

    for subvolume in subvolume_list:
        pmb.chroot.root(["btrfs", "subvol", "create", f"{mountpoint}/{subvolume}"])

    # Set the default root subvolume to be separate from top level btrfs
    # subvol. This lets us easily swap out current root subvol with an
    # earlier snapshot.
    pmb.chroot.root(["btrfs", "subvol", "set-default", f"{mountpoint}/@"])

    # Make directories to mount subvols onto
    pmb.chroot.root(["umount", mountpoint])
    pmb.chroot.root(["mount", device, mountpoint])
    pmb.chroot.root(
        [
            "mkdir",
            f"{mountpoint}/home",
            f"{mountpoint}/root",
            f"{mountpoint}/.snapshots",
            f"{mountpoint}/srv",
            f"{mountpoint}/var",
        ]
    )

    # snapshots contain sensitive information,
    # and should only be readable by root.
    pmb.chroot.root(["chmod", "700", f"{mountpoint}/root"])
    pmb.chroot.root(["chmod", "700", f"{mountpoint}/.snapshots"])

    # Mount subvols
    pmb.chroot.root(["mount", "-o", "subvol=@var", device, f"{mountpoint}/var"])
    pmb.chroot.root(["mount", "-o", "subvol=@home", device, f"{mountpoint}/home"])
    pmb.chroot.root(["mount", "-o", "subvol=@root", device, f"{mountpoint}/root"])
    pmb.chroot.root(["mount", "-o", "subvol=@srv", device, f"{mountpoint}/srv"])
    pmb.chroot.root(["mount", "-o", "subvol=@snapshots", device, f"{mountpoint}/.snapshots"])

    # Disable CoW for /var, to avoid write multiplication
    # and slowdown on databases, containers and VM images.
    pmb.chroot.root(["chattr", "+C", f"{mountpoint}/var"])


def format_and_mount_root(
    device: str, root_label: str, disk: PathString | None, rsync: bool, filesystem: str | None
) -> None:
    """
    :param device: root partition on install block device (e.g. /dev/installp2)
    :param root_label: label of the root partition (e.g. "pmOS_root")
    :param disk: path to disk block device (e.g. /dev/mmcblk0) or None
    """
    # Set default filesystem to ext4
    if filesystem is None:
        filesystem = "ext4"

    is_disk = not rsync and disk is not None
    format_partition_with_filesystem(device, root_label, filesystem, is_disk)

    # Mount
    mountpoint = "/mnt/install"
    logging.info("(native) mount " + device + " to " + mountpoint)
    pmb.chroot.root(["mkdir", "-p", mountpoint])
    pmb.chroot.root(["mount", device, mountpoint])

    if not rsync and filesystem == "btrfs":
        # Make flat btrfs subvolume layout
        prepare_btrfs_subvolumes(device, mountpoint)


def format(
    layout: PartitionLayout | None,
    boot_label: str,
    root_label: str,
    disk: PathString | None,
    rsync: bool,
    filesystem: str,
    full_disk_encryption: bool,
    fde_cipher: str,
    fde_iter_time: str,
) -> None:
    """
    :param layout: partition layout from get_partition_layout() or None
    :param boot_label: label of the boot partition (e.g. "pmOS_boot")
    :param root_label: label of the root partition (e.g. "pmOS_root")
    :param disk: path to disk block device (e.g. /dev/mmcblk0) or None
    """
    if layout:
        root_dev = f"/dev/installp{layout['root']}"
        boot_dev = f"/dev/installp{layout['boot']}"
    else:
        root_dev = "/dev/install"
        boot_dev = None

    if full_disk_encryption:
        format_luks_root(root_dev, fde_cipher, fde_iter_time)
        root_dev = "/dev/mapper/pm_crypt"

    format_and_mount_root(root_dev, root_label, disk, rsync, filesystem)
    if boot_dev:
        format_and_mount_boot(boot_dev, boot_label)
