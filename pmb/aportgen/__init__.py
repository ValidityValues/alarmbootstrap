# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pmb.aportgen.busybox_static
import pmb.aportgen.core
import pmb.aportgen.device
import pmb.aportgen.gcc
import pmb.aportgen.grub_efi
import pmb.aportgen.linux
import pmb.aportgen.musl
import pmb.config
import pmb.helpers.cli
from pmb.core.context import get_context
from pmb.core.pkgrepo import pkgrepo_default_path
from pmb.helpers import logging
from pmb.helpers.exceptions import NonBugError


def get_cross_package_arches(pkgname: str) -> str:
    """
    Get the arches for which we want to build cross packages.

    :param pkgname: package name, e.g. "gcc-aarch64", "gcc-x86_64"

    :returns: string of architecture(s) (space separated). It doesn't
              necessarily make sense to use Arch here given that this value gets
              used to write APKBUILD files, where the ``arch`` field can have values
              that aren't necessarily valid arches like "!armhf", "noarch", or
              "x86 x86_64".
    """
    cross_architecture = pkgname.rsplit("-", maxsplit=1)[-1]
    host_architectures = ["aarch64", "x86_64"]
    return " ".join(filter(lambda i: i != cross_architecture, host_architectures))


def properties(
    pkgname: str,
    folder: Path | None = None,
    device_category: pmb.helpers.devices.DeviceCategory | None = None,
) -> tuple[str, Path, bool]:
    """
    Get the properties for the aport generator, based on the pkgname prefix.

    Example: "musl-armhf" => ("musl", "cross", {"confirm_overwrite": False})

    :param pkgname: package name
    :param folder: optional base folder override
    :param device_category: optional device category for device/linux aports

    :returns: (prefix, folder, confirm_overwrite)
    """
    for prefix in ["busybox-static", "gcc", "musl", "grub-efi"]:
        if pkgname.startswith(prefix):
            return (prefix, folder or Path("cross"), False)

    for prefix in ["device", "linux"]:
        if pkgname.startswith(prefix):
            if not folder:
                folder = (
                    Path("device") / str(device_category) if device_category else Path("device")
                )
            return (prefix, folder, True)

    logging.info(
        "NOTE: aportgen is for generating postmarketOS specific aports, such as the cross-compiler "
        "related packages or the linux kernel fork packages."
    )
    logging.info(
        "NOTE: If you wanted to package new software in general, try"
        " 'pmbootstrap newapkbuild' to generate a template."
    )
    raise NonBugError(f"No generator available for {pkgname}!")


def generate(
    pkgname: str,
    fork_alpine: bool = False,
    fork_alpine_retain_branch: bool = False,
    folder: Path | None = None,
    device_category: pmb.helpers.devices.DeviceCategory | None = None,
) -> Path:
    if pkgname.startswith(("device", "linux")) and not device_category and not fork_alpine:
        device_category = pmb.config.ask_for_mainline_downstream()

    if fork_alpine:
        prefix, folder, confirm_overwrite = (pkgname, Path("temp"), True)
    else:
        prefix, folder, confirm_overwrite = properties(pkgname, folder, device_category)
    config = get_context().config
    path_target = pkgrepo_default_path() / folder / pkgname

    # Confirm overwrite
    if confirm_overwrite and path_target.exists():
        logging.warning(f"WARNING: Target folder already exists: {path_target}")
        if not pmb.helpers.cli.confirm("Continue and overwrite?"):
            raise NonBugError("Aborted.")

    aportgen = config.work / "aportgen"

    if aportgen.exists():
        pmb.helpers.run.user(["rm", "-r", aportgen])
    if fork_alpine:
        upstream = pmb.aportgen.core.get_upstream_aport(
            pkgname, retain_branch=fork_alpine_retain_branch
        )
        pmb.helpers.run.user(["cp", "-r", upstream, aportgen])
        pmb.aportgen.core.rewrite(pkgname)
    else:
        match prefix:
            case "busybox-static":
                pmb.aportgen.busybox_static.generate(pkgname)
            case "device":
                # Ignore mypy 'error: Argument 2 to "generate" has incompatible type
                # "DeviceCategory | None"; expected "DeviceCategory".
                # The check on the top of the page already ensures device_category is not
                # None in this case.
                pmb.aportgen.device.generate(pkgname, device_category)  # type: ignore[arg-type]
            case "gcc":
                pmb.aportgen.gcc.generate(pkgname)
            case "grub-efi":
                pmb.aportgen.grub_efi.generate(pkgname)
            case "linux":
                # Ignore mypy error; see note for "device" case above.
                pmb.aportgen.linux.generate(pkgname, device_category)  # type: ignore[arg-type]
            case "musl":
                pmb.aportgen.musl.generate(pkgname)
            case _:
                raise ValueError(f"Unexpected prefix {prefix}")

    # Move to the aports folder
    if path_target.exists():
        pmb.helpers.run.user(["rm", "-r", path_target])
    pmb.helpers.run.user(["mv", aportgen, path_target])

    logging.info(f"*** pmaport generated: {path_target}")

    return path_target
