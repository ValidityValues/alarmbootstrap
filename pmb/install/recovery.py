# Copyright 2023 Attila Szollosi
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pmb.chroot
import pmb.chroot.apk
import pmb.flasher
from pmb.core.chroot import Chroot
from pmb.helpers import logging


def create_zip(
    cipher: str,
    cmdline: str | None,
    full_disk_encryption: bool,
    no_reboot: bool,
    partition: str | None,
    recovery_flash_kernel: bool,
    recovery_install_partition: str,
    resume: bool,
    chroot: Chroot,
    device: str,
) -> None:
    """Create android recovery compatible installer zip."""
    zip_root = Path("/var/lib/postmarketos-android-recovery-installer/")
    rootfs = "/mnt/rootfs_" + device
    deviceinfo = pmb.parse.deviceinfo()
    method = deviceinfo.flash_method
    fvars = pmb.flasher.variables(
        method,
        cmdline,
        no_reboot,
        partition,
        resume,
    )

    # Install recovery installer package in buildroot
    pmb.chroot.apk.install(["postmarketos-android-recovery-installer"], chroot)

    logging.info(f"({chroot}) create recovery zip")

    for key in fvars:
        fvalue = fvars[key]

        if fvalue is None:
            continue

        pmb.flasher.check_partition_blacklist(deviceinfo, key, fvalue)

    if (
        fvars["$PARTITION_KERNEL"] is None
        or fvars["$PARTITION_INITFS"] is None
        or fvars["$PARTITION_ROOTFS"] is None
    ):
        raise AssertionError("Partitions should not be None at this point")

    # Create config file for the recovery installer
    options: dict[str, bool | str] = {
        "DEVICE": device,
        "FLASH_KERNEL": recovery_flash_kernel,
        "FLAVOR": "",
        "ISOREC": method == "heimdall-isorec",
        "KERNEL_PARTLABEL": fvars["$PARTITION_KERNEL"],
        "INITFS_PARTLABEL": fvars["$PARTITION_INITFS"],
        # Name is still "SYSTEM", not "ROOTFS" in the recovery installer
        "SYSTEM_PARTLABEL": fvars["$PARTITION_ROOTFS"],
        "INSTALL_PARTITION": recovery_install_partition,
        "CIPHER": cipher,
        "FDE": full_disk_encryption,
    }

    # Write to a temporary file
    config_temp = chroot / "tmp/install_options"
    with config_temp.open("w") as handle:
        for key, value in options.items():
            if isinstance(value, bool):
                value = str(value).lower()
            handle.write(key + "='" + value + "'\n")

    commands = [
        # Move config file from /tmp/ to zip root
        ["mv", "/tmp/install_options", "chroot/install_options"],
        # Create tar archive of the rootfs
        ["tar", "-pcf", "rootfs.tar", "--exclude", "./home", "-C", rootfs, "."],
        # Append packages keys
        ["tar", "-prf", "rootfs.tar", "-C", "/", "./etc/apk/keys"],
        # Compress with -1 for speed improvement
        ["gzip", "-f1", "rootfs.tar"],
        ["build-recovery-zip", device],
    ]
    for command in commands:
        pmb.chroot.root(command, chroot, working_dir=zip_root)
