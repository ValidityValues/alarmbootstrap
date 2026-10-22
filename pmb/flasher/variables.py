# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.config.pmaports
from pmb.core.chroot import Chroot
from pmb.core.context import get_context


def variables(
    method: str,
    cmdline: str | None,
    no_reboot: bool,
    partition: str | None,
    resume: bool,
) -> dict[str, str | None]:
    device = get_context().config.device
    deviceinfo = pmb.parse.deviceinfo()
    cmdline_ = deviceinfo.kernel_cmdline or ""
    if cmdline:
        cmdline_ = cmdline

    flash_pagesize = deviceinfo.flash_pagesize

    # TODO Remove _partition_system deviceinfo support once pmaports has been
    # updated and minimum pmbootstrap version bumped.
    # See also https://gitlab.postmarketos.org/postmarketOS/pmbootstrap/-/issues/2243

    partition_kernel: str | None
    partition_vendor_boot: str | None
    partition_rootfs: str | None

    if method.startswith("fastboot"):
        partition_kernel = deviceinfo.flash_fastboot_partition_kernel or "boot"
        partition_vendor_boot = deviceinfo.flash_fastboot_partition_vendor_boot or "vendor_boot"
        partition_rootfs = (
            deviceinfo.flash_fastboot_partition_rootfs
            or deviceinfo.flash_fastboot_partition_system
            or "userdata"
        )
        partition_vbmeta = deviceinfo.flash_fastboot_partition_vbmeta or None
        partition_dtbo = deviceinfo.flash_fastboot_partition_dtbo or None
    # Require that the partitions are specified in deviceinfo for now
    elif method.startswith("rkdeveloptool"):
        partition_kernel = deviceinfo.flash_rk_partition_kernel or None
        partition_vendor_boot = deviceinfo.flash_rk_partition_vendor_boot or None
        partition_rootfs = (
            deviceinfo.flash_rk_partition_rootfs or deviceinfo.flash_rk_partition_system or None
        )
        partition_vbmeta = None
        partition_dtbo = None
    elif method.startswith("mtkclient"):
        partition_kernel = deviceinfo.flash_mtkclient_partition_kernel or "boot"
        partition_vendor_boot = deviceinfo.flash_mtkclient_partition_vendor_boot or "vendor_boot"
        partition_rootfs = deviceinfo.flash_mtkclient_partition_rootfs or "userdata"
        partition_vbmeta = deviceinfo.flash_mtkclient_partition_vbmeta or None
        partition_dtbo = deviceinfo.flash_mtkclient_partition_dtbo or None
    else:
        partition_kernel = deviceinfo.flash_heimdall_partition_kernel or "KERNEL"
        partition_vendor_boot = (
            deviceinfo.flash_heimdall_partition_vendor_boot or None
        )  # TODO: is there a default name?
        partition_rootfs = (
            deviceinfo.flash_heimdall_partition_rootfs
            or deviceinfo.flash_heimdall_partition_system
            or "SYSTEM"
        )
        partition_vbmeta = deviceinfo.flash_heimdall_partition_vbmeta or None
        partition_dtbo = deviceinfo.flash_heimdall_partition_dtbo or None

    if partition:
        # Only one operation is done at same time so it doesn't matter
        # sharing the arg
        partition_kernel = partition
        partition_vendor_boot = partition
        partition_rootfs = partition
        partition_vbmeta = partition
        partition_dtbo = partition

    dtb = deviceinfo.dtb + ".dtb"

    no_reboot_ = ""
    if no_reboot:
        no_reboot_ = "--no-reboot"

    resume_ = ""
    if resume:
        resume_ = "--resume"

    fvars = {
        "$BOOT": "/mnt/rootfs_" + device + "/boot",
        "$DTB": dtb,
        "$FLAVOR": "",
        "$IMAGE_SPLIT_BOOT": "/home/pmos/rootfs/" + device + "-boot.img",
        "$IMAGE_SPLIT_ROOT": "/home/pmos/rootfs/" + device + "-root.img",
        "$IMAGE": "/home/pmos/rootfs/" + device + ".img",
        "$KERNEL_CMDLINE": cmdline_,
        "$PARTITION_KERNEL": partition_kernel,
        "$PARTITION_VENDOR_BOOT": partition_vendor_boot,
        "$PARTITION_INITFS": deviceinfo.flash_heimdall_partition_initfs or "RECOVERY",
        "$PARTITION_ROOTFS": partition_rootfs,
        "$PARTITION_VBMETA": partition_vbmeta,
        "$PARTITION_DTBO": partition_dtbo,
        "$FLASH_PAGESIZE": flash_pagesize,
        "$RECOVERY_ZIP": f"/mnt/{Chroot.buildroot(deviceinfo.arch)}"
        "/var/lib/postmarketos-android-recovery-installer"
        f"/pmos-{device}.zip",
        "$UUU_SCRIPT": f"/mnt/{Chroot.rootfs(deviceinfo.codename)}/usr/share/uuu/flash_script.lst",
        "$NO_REBOOT": no_reboot_,
        "$RESUME": resume_,
    }

    return fvars
