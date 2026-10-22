# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pmb.chroot
import pmb.core.dps
import pmb.helpers.file
import pmb.install.losetup
from pmb.core import Chroot
from pmb.helpers import logging
from pmb.types import PartitionLayout


# FIXME (#2324): this function drops disk to a string because it's easier
# to manipulate, this is probably bad.
def partitions_mount(device: str, layout: PartitionLayout, disk: Path | None) -> None:
    """
    Mount blockdevices of partitions inside native chroot

    :param layout: partition layout from get_partition_layout()
    :param disk: path to disk block device (e.g. /dev/mmcblk0) or None
    """
    if not disk:
        img_path = Path("/home/pmos/rootfs") / f"{device}.img"
        disk = pmb.install.losetup.device_by_back_file(img_path)

    logging.info(f"Mounting partitions of {disk} inside the chroot")

    # Devices ending with a number have a "p" before the partition number,
    # /dev/sda1 has no "p", but /dev/mmcblk0p1 has. See add_partition() in
    # block/partitions/core.c of linux.git.
    partition_prefix = str(disk)
    if str.isdigit(disk.name[-1:]):
        partition_prefix = f"{disk}p"

    partitions = [layout["root"]]

    if layout["prep"]:
        partitions += [layout["prep"]]

    if layout["boot"]:
        partitions += [layout["boot"]]

    if layout["kernel"]:
        partitions += [layout["kernel"]]

    for i in partitions:
        source = Path(f"{partition_prefix}{i}")
        pmb.helpers.file.wait_until_exists(source)
        target = Chroot.native() / "dev" / f"installp{i}"
        pmb.helpers.mount.bind_file(source, target)
        target = Chroot.native() / "dev" / f"{disk.name}p{i}"
        pmb.helpers.mount.bind_file(source, target)


def partition(layout: PartitionLayout, size_boot: int) -> None:
    """
    Partition /dev/install and create /dev/install{p1,p2,p3}:
    * /dev/installp1: boot
    * /dev/installp2: root (or reserved space)
    * /dev/installp3: (root, if reserved space > 0)

    :param layout: partition layout from get_partition_layout()
    :param size_boot: size of the boot partition in MiB
    """
    # Convert to MB and print info
    mb_boot = f"{size_boot}M"
    mb_root_start = f"{size_boot}M"
    logging.info(f"(native) partition /dev/install (boot: {mb_boot})")

    filesystem = (
        pmb.parse.deviceinfo().boot_filesystem
        or pmb.parse.deviceinfo_schema_default_boot_filesystem()
    )

    # Actual partitioning with 'parted'. Using check=False, because parted
    # sometimes "fails to inform the kernel". In case it really failed with
    # partitioning, the follow-up mounting/formatting will not work, so it
    # will stop there (see #463).
    boot_part_start = pmb.parse.deviceinfo().boot_part_start or "2048"

    partition_type = pmb.parse.deviceinfo().partition_type or "gpt"

    commands = [
        ["mktable", partition_type],
        ["mkpart", "primary", filesystem, boot_part_start + "s", mb_boot],
    ]

    arch = str(pmb.parse.deviceinfo().arch)

    commands += [["mkpart", "primary", mb_root_start, "100%"]]
    if partition_type.lower() == "gpt":
        commands += [
            ["type", str(layout["root"]), pmb.core.dps.root[arch][1]],
            # esp is an alias for boot on GPT
            ["set", str(layout["boot"]), "esp", "on"],
            ["type", str(layout["boot"]), pmb.core.dps.boot["esp"][1]],
        ]
    # Some devices still use MBR and will not work with only esp set
    elif partition_type.lower() == "msdos":
        commands += [["set", str(layout["boot"]), "boot", "on"]]

    for command in commands:
        pmb.chroot.root(["parted", "-s", "/dev/install", *command], check=False)


def partition_cgpt(layout: PartitionLayout, size_boot: int) -> None:
    """
    This function does similar functionality to partition(), but this
    one is for ChromeOS devices which use special GPT. We don't follow
    the Discoverable Partitions Specification here for that exact reason.

    :param layout: partition layout from get_partition_layout()
    :param size_boot: size of the boot partition in MiB
    """
    pmb.chroot.apk.install(["cgpt"], Chroot.native(), build=False)

    deviceinfo = pmb.parse.deviceinfo()

    if deviceinfo.cgpt_kpart_start is None or deviceinfo.cgpt_kpart_size is None:
        raise RuntimeError("cgpt_kpart_start or cgpt_kpart_size not found in deviceinfo")

    cgpt = {
        # or 0 shouldn't be needed since we None check just above, but mypy isn't that smart
        # so we add it to make it happy
        "kpart_start": pmb.parse.deviceinfo().cgpt_kpart_start or "0",
        "kpart_size": pmb.parse.deviceinfo().cgpt_kpart_size or "0",
    }

    # Convert to MB and print info
    mb_boot = f"{size_boot}M"
    logging.info(f"(native) partition /dev/install (boot: {mb_boot})")

    boot_part_start = str(int(cgpt["kpart_start"]) + int(cgpt["kpart_size"]))

    # Convert to sectors
    s_boot = str(int(size_boot * 1024 * 1024 / 512))
    s_root_start = str(int(int(boot_part_start) + int(s_boot)))

    commands = [
        ["parted", "-s", "/dev/install", "mktable", "gpt"],
        ["cgpt", "create", "/dev/install"],
        [
            "cgpt",
            "add",
            "-i",
            str(layout["kernel"]),
            "-t",
            "kernel",
            "-b",
            cgpt["kpart_start"],
            "-s",
            cgpt["kpart_size"],
            "-l",
            "pmOS_kernel",
            "-S",
            "1",  # Successful flag
            "-T",
            "5",  # Tries flag
            "-P",
            "10",  # Priority flag
            "/dev/install",
        ],
        [
            "cgpt",
            "add",
            # pmOS_boot is second partition, the first will be ChromeOS kernel
            # partition
            "-i",
            str(layout["boot"]),  # Partition number
            "-t",
            "efi",  # Mark this partition as bootable for u-boot
            "-b",
            boot_part_start,
            "-s",
            s_boot,
            "-l",
            "pmOS_boot",
            "/dev/install",
        ],
    ]

    dev_size = pmb.chroot.root(["blockdev", "--getsz", "/dev/install"], output_return=True)
    # 33: Sec GPT table (32) + Sec GPT header (1)
    root_size = str(int(dev_size) - int(s_root_start) - 33)

    commands += [
        [
            "cgpt",
            "add",
            "-i",
            str(layout["root"]),
            "-t",
            "data",
            "-b",
            s_root_start,
            "-s",
            root_size,
            "-l",
            "pmOS_root",
            "/dev/install",
        ],
        ["partx", "-a", "/dev/install"],
    ]

    for command in commands:
        pmb.chroot.root(command, check=False)


def partition_prep(layout: PartitionLayout, size_boot: int) -> None:
    """
    Partition /dev/install and create /dev/installp{1,2,3}:
    * /dev/installp1: PReP boot
    * /dev/installp2: boot
    * /dev/installp3: root

    :param layout: partition layout from get_partition_layout()
    :param size_boot: size of the boot partition in MiB
    """
    logging.info(f"(native) partition /dev/install (PReP boot: 8MB, boot: {size_boot}MB)")

    # Actual partitioning with 'parted'. Using check=False, because parted
    # sometimes "fails to inform the kernel". In case it really failed with
    # partitioning, the follow-up mounting/formatting will not work, so it
    # will stop there (see #463).

    # Only very few OpenFirmware platforms seem to support GPT
    partition_type = pmb.parse.deviceinfo().partition_type or "msdos"

    commands = [
        ["mktable", partition_type],
        ["mkpart", "primary", "1MiB", "9MiB"],
        ["mkpart", "primary", "9MiB", f"{size_boot + 9}MiB"],
        ["mkpart", "primary", f"{size_boot + 9}MiB", "100%"],
        ["set", str(layout["prep"]), "PREP", "on"],
        ["set", str(layout["prep"]), "boot", "on"],
    ]

    arch = str(pmb.parse.deviceinfo().arch)

    if partition_type.lower() == "gpt":
        commands += [
            ["type", str(layout["prep"]), pmb.core.dps.boot["prep"][1]],
            ["set", str(layout["boot"]), "esp", "on"],
            ["type", str(layout["boot"]), pmb.core.dps.boot["esp"][1]],
            ["type", str(layout["root"]), pmb.core.dps.root[arch][1]],
        ]
    elif partition_type.lower() == "msdos":
        commands += [["type", str(layout["prep"]), "0x41"]]  # PReP boot type
        commands += [["type", str(layout["boot"]), "0xEF"]]  # ESP type

    for command in commands:
        pmb.chroot.root(["parted", "-s", "/dev/install", *command], check=False)
