# Copyright 2023 Clayton Craft
# SPDX-License-Identifier: GPL-3.0-or-later
import os

import pmb.helpers.pmaports
import pmb.parse
from pmb.core.arch import Arch
from pmb.core.pkgrepo import pkgrepo_iglob
from pmb.helpers import logging
from pmb.helpers.exceptions import NonBugError
from pmb.types import WithExtraRepos


def validate_ui_options(ui: str) -> None:
    if check_option(ui, "pmb:default-systemd") and check_option(ui, "pmb:default-openrc"):
        raise NonBugError(
            f"ERROR: UI {ui} has both pmb:default-systemd and pmb:default-openrc in the APKBUILD options. Only one can be used at a time!"
        )

    if check_option(ui, "pmb:default-systemd") and not check_option(ui, "pmb:support-systemd"):
        raise NonBugError(
            f"ERROR: UI {ui} has pmb:default-systemd without pmb:support-systemd the APKBUILD options!"
        )

    if check_option(ui, "pmb:default-openrc") and not check_option(ui, "pmb:support-openrc"):
        raise NonBugError(
            f"ERROR: UI {ui} has pmb:default-openrc without pmb:support-openrc the APKBUILD options!"
        )


def list_ui(arch: Arch) -> list[tuple[str, str]]:
    """
    Get all UIs, for which aports are available with their description.

    :param arch: device architecture, for which the UIs must be available
    :returns: [("none", "No graphical..."), ("weston", "Wayland reference...")]
    """
    ret = [
        (
            "none",
            (
                "Bare minimum OS image for testing and manual"
                ' customization. The "console" UI should be selected if'
                " a graphical UI is not desired."
            ),
        )
    ]
    for path in sorted(pkgrepo_iglob("main/postmarketos-ui-*")):
        try:
            apkbuild = pmb.parse.apkbuild(path)
        except FileNotFoundError as exception:
            logging.debug("Skipping UI directory without APKBUILD '%s' (%s)", path, exception)
            continue
        ui = os.path.basename(path).split("-", 2)[2]
        validate_ui_options(ui)
        if arch in Arch.from_arch_field(apkbuild["arch"]):
            ret.append((ui, apkbuild["pkgdesc"]))
    return ret


def check_option(
    ui: str,
    option: str,
    must_exist: bool = True,
    with_extra_repos: WithExtraRepos = WithExtraRepos.DEFAULT,
) -> bool:
    """
    Check if an option, such as pmb:drm, is inside an UI's APKBUILD.

    If must_exist is set to False, False will be returned if the UI doesn't exist.
    """
    if ui == "none":
        # Users can select "none" as UI in "pmbootstrap init", which does not
        # have a UI package.
        return False

    pkgname = f"postmarketos-ui-{ui}"
    apkbuild = pmb.helpers.pmaports.get(
        pkgname, must_exist, subpackages=False, with_extra_repos=with_extra_repos
    )
    return option in apkbuild["options"] if apkbuild is not None else False
