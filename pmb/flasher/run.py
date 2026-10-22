# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.chroot.initfs
import pmb.flasher
from pmb.helpers.exceptions import NonBugError
from pmb.parse.deviceinfo import Deviceinfo
from pmb.types import RunOutputTypeDefault


def check_partition_blacklist(deviceinfo: Deviceinfo, key: str, value: str) -> None:
    if not key.startswith("$PARTITION_"):
        return

    name = deviceinfo.name
    if value in (deviceinfo.partition_blacklist or "").split(","):
        raise RuntimeError(
            f"'{value}' partition is blacklisted from being flashed! See the"
            f" {name} device wiki page for more information."
        )


def run(
    deviceinfo: Deviceinfo,
    method: str,
    action: str,
    cmdline: str | None = None,
    no_reboot: bool = False,
    partition: str | None = None,
    resume: bool = False,
) -> None:
    pmb.flasher.init(deviceinfo.codename, method)

    # Verify action
    cfg = pmb.config.flashers[method]
    if not isinstance(cfg["actions"], dict):
        raise TypeError(f"Flashers misconfigured! {method} key 'actions' should be a dictionary")
    if action not in cfg["actions"]:
        raise RuntimeError(
            f"action {action} is not configured for method {method}! You can"
            " use the '--method' option to specify a different flash method."
            " See also: <https://wiki.postmarketos.org/wiki/Deviceinfo_flash_methods>"
        )

    # Variable setup
    fvars = pmb.flasher.variables(method, cmdline, no_reboot, partition, resume)

    # vbmeta flasher requires vbmeta partition to be explicitly specified
    if action == "flash_vbmeta" and not fvars["$PARTITION_VBMETA"]:
        raise RuntimeError(
            "Your device does not have 'vbmeta' partition specified; set"
            " 'deviceinfo_flash_fastboot_partition_vbmeta' or"
            " 'deviceinfo_flash_heimdall_partition_vbmeta' in deviceinfo file. See also:"
            " <https://postmarketos.org/deviceinfo>"
        )

    if (
        action == "flash_vendorboot"
        and deviceinfo.header_version
        and deviceinfo.header_version <= 2
    ):
        raise NonBugError(
            "'vendor_boot' is only supported with 'deviceinfo_header_version'"
            " >= 3. See also: <https://postmarketos.org/deviceinfo>"
        )

    # dtbo flasher requires dtbo partition to be explicitly specified
    if action == "flash_dtbo" and not fvars["$PARTITION_DTBO"]:
        raise RuntimeError(
            "Your device does not have 'dtbo' partition specified; set"
            " 'deviceinfo_flash_fastboot_partition_dtbo' in deviceinfo file."
            " See also: <https://postmarketos.org/deviceinfo>"
        )

    if no_reboot and ("flash" not in action or method != "heimdall-bootimg"):
        raise RuntimeError(
            "The '--no-reboot' option is only supported when flashing with heimall-bootimg."
        )

    if resume and ("flash" not in action or method != "heimdall-bootimg"):
        raise RuntimeError(
            "The '--resume' option is only supported when flashing with heimall-bootimg."
        )

    # Run the commands of each action
    for command in cfg["actions"][action]:
        # Variable replacement
        for key, value in fvars.items():
            for i in range(len(command)):
                if key in command[i]:
                    if value is None:
                        raise RuntimeError(
                            f"Variable {key} found in action {action} for"
                            f" method {method}, but the value for this"
                            " variable is None! Is that missing in your"
                            " deviceinfo?"
                        )
                    check_partition_blacklist(deviceinfo, key, value)
                    command[i] = command[i].replace(key, value)

        # Remove cmdline if it's empty
        if "--cmdline" in command:
            i = command.index("--cmdline")
            if i + 1 < len(command) and not command[i + 1]:
                command.pop(i)  # "--cmdline"
                command.pop(i)  # ""

        # Remove empty strings
        command = [x for x in command if x != ""]
        # Run the action
        pmb.chroot.root(command, output=RunOutputTypeDefault.INTERACTIVE)
