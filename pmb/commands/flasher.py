# Copyright 2023 Oliver Smith
# Copyright 2024 Stefan Hansson
# SPDX-License-Identifier: GPL-3.0-or-later

import pmb.parse.deviceinfo
from pmb.core.context import get_context
from pmb.flasher.frontend import flash_lk2nd, kernel, list_flavors, rootfs, sideload
from pmb.helpers import logging


def flasher(
    action: str,
    autoinstall: bool,
    cmdline: str | None,
    flash_method: str,
    no_reboot: bool,
    partition: str | None,
    resume: bool,
) -> None:
    context = get_context()
    device = context.config.device
    deviceinfo = pmb.parse.deviceinfo()
    method = flash_method or deviceinfo.flash_method

    if method == "none" and action in ["boot", "flash_kernel", "flash_rootfs", "flash_lk2nd"]:
        logging.info("This device doesn't support any flash method.")
        return

    if action in ["boot", "flash_kernel"]:
        kernel(
            deviceinfo,
            method,
            action == "boot",
            autoinstall,
            cmdline=cmdline,
            no_reboot=no_reboot,
            partition=partition,
            resume=resume,
        )
    elif action == "flash_rootfs":
        rootfs(
            deviceinfo,
            method,
            cmdline=cmdline,
            no_reboot=no_reboot,
            partition=partition,
            resume=resume,
        )
    elif action == "flash_vbmeta":
        logging.info("(native) flash vbmeta.img with verity disabled flag")
        pmb.flasher.run(
            deviceinfo,
            method,
            "flash_vbmeta",
            cmdline=cmdline,
            no_reboot=no_reboot,
            partition=partition,
            resume=resume,
        )
    elif action == "flash_dtbo":
        logging.info("(native) flash dtbo image")
        pmb.flasher.run(
            deviceinfo,
            method,
            "flash_dtbo",
            cmdline=cmdline,
            no_reboot=no_reboot,
            partition=partition,
            resume=resume,
        )
    elif action == "flash_lk2nd":
        flash_lk2nd(
            deviceinfo,
            method,
            cmdline=cmdline,
            no_reboot=no_reboot,
            partition=partition,
            resume=resume,
        )
    elif action == "list_flavors":
        list_flavors(device)
    elif action == "list_devices":
        pmb.flasher.run(
            deviceinfo,
            method,
            "list_devices",
            cmdline=cmdline,
            no_reboot=no_reboot,
            partition=partition,
            resume=resume,
        )
    elif action == "sideload":
        sideload(
            deviceinfo,
            method,
            cmdline=cmdline,
            no_reboot=no_reboot,
            partition=partition,
            resume=resume,
        )
