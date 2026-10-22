# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path, PurePath

import pmb.helpers
import pmb.helpers.run
from pmb.core import Chroot
from pmb.types import PathString


def ismount(folder: Path) -> bool:
    """
    Ismount() implementation that works for mount --bind.

    Workaround for: https://bugs.python.org/issue29707
    """
    folder = folder.resolve()
    with open("/proc/mounts") as handle:
        for line in handle:
            words = line.split()
            if len(words) >= 2 and Path(words[1]) == folder:
                return True
            if words[0] == str(folder):
                return True
    return False


def bind(
    source: PathString, destination: Path, create_folders: bool = True, umount: bool = False
) -> None:
    """
    Mount --bind a folder and create necessary directory structure.

    :param umount: when destination is already a mount point, umount it first.
    """
    # Check/umount destination
    if ismount(destination):
        if umount:
            umount_all(destination)
        else:
            return

    # Check/create folders
    for path in [source, destination]:
        if os.path.exists(path):
            continue
        if create_folders:
            pmb.helpers.run.root(["mkdir", "-p", path])
        else:
            raise RuntimeError(f"Mount failed, folder does not exist: {path}")

    # Actually mount the folder
    pmb.helpers.run.root(["mount", "--bind", source, destination])

    # Verify that it has worked
    if not ismount(destination):
        raise RuntimeError(f"Mount failed: {source} -> {destination}")


def bind_file(source: Path, destination: Path, create_folders: bool = False) -> None:
    """Mount a file with the --bind option, and create the destination file, if necessary."""
    # Skip existing mountpoint
    if ismount(destination):
        return

    # Create empty file
    if not destination.exists():
        if create_folders:
            dest_dir: Path = destination.parent
            if not dest_dir.is_dir():
                pmb.helpers.run.root(["mkdir", "-p", dest_dir])

        pmb.helpers.run.root(["touch", destination])

    # Mount
    pmb.helpers.run.root(["mount", "--bind", source, destination])


def umount_all_list(prefix: Path, source: Path = Path("/proc/mounts")) -> list[Path]:
    """
    Parse `/proc/mounts` for all folders beginning with a prefix.

    :source: can be changed for testcases

    :returns: a list of folders that need to be umounted

    """
    ret = []
    prefix = prefix.resolve()
    with source.open() as handle:
        for line in handle:
            words = line.split()
            if len(words) < 2:
                raise RuntimeError(f"Failed to parse line in {source}: {line}")
            mountpoint = Path(words[1].replace(r"\040(deleted)", ""))
            if mountpoint.is_relative_to(prefix):  # is subpath
                ret.append(mountpoint)
    ret.sort(reverse=True)
    return ret


def umount_all(folder: Path) -> None:
    """Umount all folders that are mounted inside a given folder."""
    for mountpoint in umount_all_list(folder):
        pmb.helpers.run.root(["umount", mountpoint])
        if ismount(mountpoint):
            raise RuntimeError(f"Failed to umount: {mountpoint}")


def mount_device_rootfs(chroot_rootfs: Chroot, chroot_base: Chroot = Chroot.native()) -> PurePath:
    """
    Mount the device rootfs.

    :param chroot_rootfs: the chroot where the rootfs that will be
                          installed on the device has been created (e.g.
                          "rootfs_qemu-amd64")
    :param chroot_base: the chroot rootfs mounted to
    :returns: the mountpoint (relative to the chroot)
    """
    mountpoint = PurePath("/mnt", str(chroot_rootfs))
    pmb.helpers.mount.bind(chroot_rootfs.path, chroot_base / mountpoint)
    return mountpoint
