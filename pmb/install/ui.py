# Copyright 2023 Dylan Van Assche
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.helpers.pmaports
from pmb.core import Config
from pmb.helpers import logging


def get_groups(config: Config) -> list[str]:
    """
    Get all groups to which the user additionally must be added.
    The list of groups are listed in _pmb_groups of the UI and
    UI-extras package.

    :returns: list of groups, e.g. ["feedbackd", "udev"]
    """
    ret: list[str] = []
    if config.ui == "none":
        return ret

    # UI package
    meta = f"postmarketos-ui-{config.ui}"
    apkbuild = pmb.helpers.pmaports.get(meta)
    groups = apkbuild["_pmb_groups"]
    if groups:
        logging.debug(f"{meta}: install _pmb_groups: {', '.join(groups)}")
        ret += groups

    # UI-extras subpackage
    meta_extras = f"{meta}-extras"
    if config.ui_extras and meta_extras in apkbuild["subpackages"]:
        groups = apkbuild["subpackages"][meta_extras]["_pmb_groups"]
        if groups:
            logging.debug(f"{meta_extras}: install _pmb_groups: {', '.join(groups)}")
            ret += groups

    return ret
