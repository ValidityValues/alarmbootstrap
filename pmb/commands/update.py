# Copyright 2026 Hugo Posnic
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.helpers.repo
from pmb.core.arch import Arch
from pmb.helpers import logging


def update(arch: Arch | None, non_existing: str) -> None:
    existing_only = not non_existing
    indexes_downloaded = False
    if arch is None:
        for sup_arch in Arch.supported_binary():
            if pmb.helpers.repo.update(sup_arch, True, existing_only):
                indexes_downloaded = True
    elif pmb.helpers.repo.update(arch, True, existing_only):
        indexes_downloaded = True
    if not indexes_downloaded:
        logging.info(
            "No APKINDEX files exist, so none have been updated."
            " The pmbootstrap command downloads the APKINDEX files on"
            " demand."
        )
        logging.info(
            "If you want to force downloading the APKINDEX files for"
            " all architectures (not recommended), use:"
            " pmbootstrap update --non-existing"
        )
