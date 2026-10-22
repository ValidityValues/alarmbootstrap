# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import PosixPath

import pmb.chroot.apk
import pmb.chroot.initfs
import pmb.chroot.other
import pmb.config
import pmb.flasher
import pmb.helpers.frontend
import pmb.helpers.mount
import pmb.parse.kconfig
from pmb.core import Chroot, ChrootType
from pmb.core.context import get_context
from pmb.helpers import logging
from pmb.helpers.exceptions import NonBugError
from pmb.parse.deviceinfo import Deviceinfo
from pmb.types import RunOutputTypeDefault


def kernel(
    deviceinfo: Deviceinfo,
    method: str,
    boot: bool = False,
    autoinstall: bool = False,
    cmdline: str | None = None,
    no_reboot: bool = False,
    partition: str | None = None,
    resume: bool = False,
) -> None:
    # Rebuild the initramfs, just to make sure (see #69)
    flavor = pmb.helpers.frontend._parse_flavor(deviceinfo.codename, autoinstall)
    if autoinstall:
        pmb.chroot.initfs.build(Chroot(ChrootType.ROOTFS, deviceinfo.codename))

    # deviceinfo.header_version >= 3 == GKI == has / needs vendor_boot
    is_gki = deviceinfo.header_version and deviceinfo.header_version >= 3

    # Check kernel config
    pmb.parse.kconfig.check(flavor, must_exist=False)

    # Do not allow header_version >= 3 for non-fastboot, since the correct way to flash
    # vendor_boot with other flash methods is unknown as of 2025-08.
    if not deviceinfo.flash_method == "fastboot" and (
        deviceinfo.header_version and deviceinfo.header_version >= 3
    ):
        raise NonBugError(
            "deviceinfo_header_version >= 3 is currently only supported with fastboot. See also:"
            " <https://postmarketos.org/deviceinfo>"
        )

    # Generate the paths and run the flasher
    if boot:
        logging.info("(native) boot " + flavor + " kernel")
        pmb.flasher.run(
            deviceinfo,
            method,
            "boot_gki" if is_gki else "boot",
            cmdline=cmdline,
            no_reboot=no_reboot,
            partition=partition,
            resume=resume,
        )
    else:
        logging.info("(native) flash kernel " + flavor)
        pmb.flasher.run(
            deviceinfo,
            method,
            "flash_kernel",
            cmdline=cmdline,
            no_reboot=no_reboot,
            partition=partition,
            resume=resume,
        )
        if is_gki:
            pmb.flasher.run(
                deviceinfo,
                method,
                "flash_vendorboot",
                cmdline=cmdline,
                no_reboot=no_reboot,
                partition=partition,
                resume=resume,
            )

    logging.info("You will get an IP automatically assigned to your USB interface shortly.")
    logging.info("Then you can connect to your device using ssh after pmOS has booted:")
    logging.info(f"ssh {get_context().config.user}@{pmb.config.default_ip}")
    logging.info(
        "NOTE: If you enabled full disk encryption, you should make"
        " sure that Unl0kr has been properly configured for your"
        " device"
    )


def list_flavors(device: str) -> None:
    chroot = Chroot(ChrootType.ROOTFS, device)
    logging.info(f"({chroot}) installed kernel flavors:")
    logging.info("* " + str(pmb.chroot.other.kernel_flavor_installed(chroot)))


def rootfs(
    deviceinfo: Deviceinfo,
    method: str,
    cmdline: str | None = None,
    no_reboot: bool = False,
    partition: str | None = None,
    resume: bool = False,
) -> None:
    # Generate rootfs, install flasher
    suffix = ".img"
    if pmb.config.flashers.get(method, {}).get("split", False):
        suffix = "-root.img"

    img_path = Chroot.native() / "home/pmos/rootfs" / f"{deviceinfo.codename}{suffix}"
    if not img_path.exists():
        raise NonBugError(
            "The rootfs has not been generated yet, please run 'pmbootstrap install' first."
        )

    # Do not flash if using fastboot & image is too large
    if method.startswith("fastboot") and deviceinfo.flash_fastboot_max_size:
        img_size = img_path.stat().st_size / 1024**2
        max_size = int(deviceinfo.flash_fastboot_max_size)
        if img_size > max_size:
            raise RuntimeError("The rootfs is too large for fastboot to flash.")

    # Run the flasher
    logging.info("(native) flash rootfs image")
    pmb.flasher.run(
        deviceinfo,
        method,
        "flash_rootfs",
        cmdline=cmdline,
        no_reboot=no_reboot,
        partition=partition,
        resume=resume,
    )


def list_devices(
    deviceinfo: Deviceinfo,
    method: str,
    cmdline: str | None = None,
    no_reboot: bool = False,
    partition: str | None = None,
    resume: bool = False,
) -> None:
    # pmb.flasher.run provides user-facing error messages for unsupported
    # flags, hence why we pass them here despite them being unused
    pmb.flasher.run(
        deviceinfo,
        method,
        "list_devices",
        cmdline=cmdline,
        no_reboot=no_reboot,
        partition=partition,
        resume=resume,
    )


def sideload(
    deviceinfo: Deviceinfo,
    method: str,
    cmdline: str | None = None,
    no_reboot: bool = False,
    partition: str | None = None,
    resume: bool = False,
) -> None:
    # Install depends
    pmb.flasher.install_depends(method)

    # Mount the buildroot
    chroot = Chroot.buildroot(deviceinfo.arch)
    mountpoint = "mnt" / PosixPath(str(chroot))
    pmb.helpers.mount.bind(chroot.path, Chroot.native().path / mountpoint)

    # Missing recovery zip error
    if not (
        Chroot.native().path
        / mountpoint
        / "var/lib/postmarketos-android-recovery-installer"
        / f"pmos-{deviceinfo.codename}.zip"
    ).exists():
        raise RuntimeError(
            "The recovery zip has not been generated yet,"
            " please run 'pmbootstrap install' with the"
            " '--android-recovery-zip' parameter first!"
        )

    pmb.flasher.run(
        deviceinfo,
        method,
        "sideload",
        cmdline=cmdline,
        no_reboot=no_reboot,
        partition=partition,
        resume=resume,
    )


def flash_lk2nd(
    deviceinfo: Deviceinfo,
    method: str,
    cmdline: str | None = None,
    no_reboot: bool = False,
    partition: str | None = None,
    resume: bool = False,
) -> None:
    if method == "fastboot":
        # In the future this could be expanded to use "fastboot flash lk2nd $img"
        # which reflashes/updates lk2nd from itself. For now let the user handle this
        # manually since supporting the codepath with heimdall requires more effort.
        pmb.flasher.init(deviceinfo.codename, method)
        logging.info("(native) checking current fastboot product")
        output = pmb.chroot.root(
            ["fastboot", "getvar", "product"],
            output=RunOutputTypeDefault.INTERACTIVE,
            output_return=True,
        )
        # Variable "product" is e.g. "LK2ND_MSM8974" or "lk2nd-msm8226" depending
        # on the lk2nd version.
        if "lk2nd" in output.lower():
            raise RuntimeError(
                "You are currently running lk2nd. Please reboot into the regular"
                " bootloader mode to re-flash lk2nd."
            )

    # Get the lk2nd package (which is a dependency of the device package)
    device_pkg = f"device-{deviceinfo.codename}"
    apkbuild = pmb.helpers.pmaports.get(device_pkg)
    if not apkbuild:
        raise RuntimeError(f"Failed to find {device_pkg} in pmaports")
    lk2nd_pkg = None
    for dep in apkbuild["depends"]:
        if dep.startswith("lk2nd"):
            lk2nd_pkg = dep
            break

    # If not found, also check subpackages
    if not lk2nd_pkg:
        for subpackage in apkbuild["subpackages"]:
            for dep in apkbuild["subpackages"][subpackage]["depends"]:
                if dep.startswith("lk2nd"):
                    lk2nd_pkg = dep
                    break

    if not lk2nd_pkg:
        raise RuntimeError(f"{device_pkg} does not depend on any lk2nd package")

    suffix = Chroot(ChrootType.ROOTFS, deviceinfo.codename)
    pmb.chroot.apk.install([lk2nd_pkg], suffix)

    logging.info("(native) flash lk2nd image")
    pmb.flasher.run(
        deviceinfo,
        method,
        "flash_lk2nd",
        cmdline=cmdline,
        no_reboot=no_reboot,
        partition=partition,
        resume=resume,
    )
