# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import time
from pathlib import Path

import pmb.chroot
import pmb.helpers.mount
import pmb.helpers.run
from pmb.core import Chroot
from pmb.core.context import get_context
from pmb.helpers import logging
from pmb.types import PathString


def init() -> None:
    if not Path("/sys/module/loop").is_dir():
        pmb.helpers.run.root(["modprobe", "loop"])
    for loopdevice in Path("/dev/").glob("loop*"):
        if loopdevice.is_dir():
            continue
        pmb.helpers.mount.bind_file(loopdevice, Chroot.native() / loopdevice)


def mount(img_path: Path, _sector_size: int | None = None) -> Path:
    """:param img_path: Path to the img file inside native chroot."""
    logging.debug(f"(native) mount {img_path} (loop)")

    # Try to mount multiple times (let the kernel module initialize #1594)
    for i in range(5):
        # Retry
        if i > 0:
            logging.debug("loop module might not be initialized yet, retry in one second...")
            time.sleep(1)

        # Mount and return on success
        init()

        sector_size = None
        if _sector_size:
            sector_size = str(_sector_size)
        sector_size = sector_size or pmb.parse.deviceinfo().rootfs_image_sector_size

        losetup_cmd: list[PathString] = ["losetup", "-f", "-P", img_path]
        if sector_size:
            losetup_cmd += ["-b", str(int(sector_size))]

        pmb.chroot.root(losetup_cmd, check=False)

        try:
            return device_by_back_file(img_path)
        except RuntimeError:
            if i == 4:
                raise

    raise AssertionError("This should never be reached")


def device_by_back_file(back_file: Path) -> Path:
    """Get the /dev/loopX device that points to a specific image file."""
    # Get list from losetup
    losetup_output = pmb.chroot.root(["losetup", "--json", "--list"], output_return=True)
    if not losetup_output:
        raise RuntimeError("losetup failed")

    # Find the back_file
    losetup = json.loads(losetup_output)
    for loopdevice in losetup["loopdevices"]:
        if loopdevice["back-file"] is not None and Path(loopdevice["back-file"]) == back_file:
            return Path(loopdevice["name"])
    raise RuntimeError(f"Failed to find loop device for {back_file}")


def umount(img_path: Path) -> None:
    """:param img_path: Path to the img file inside native chroot."""
    device: Path
    try:
        device = device_by_back_file(img_path)
    except RuntimeError:
        return
    logging.debug(f"(native) umount {device}")
    pmb.chroot.root(["losetup", "-d", device])


def detach_all() -> None:
    """Detach all loop devices used by pmbootstrap"""
    losetup_output = pmb.helpers.run.root(["losetup", "--json", "--list"], output_return=True)
    if not losetup_output:
        return
    losetup = json.loads(losetup_output)
    work = get_context().config.work
    for loopdevice in losetup["loopdevices"]:
        if Path(loopdevice["back-file"]).is_relative_to(work):
            pmb.helpers.run.root(["kpartx", "-d", loopdevice["name"]], check=False)
            pmb.helpers.run.root(["losetup", "-d", loopdevice["name"]])
    return
