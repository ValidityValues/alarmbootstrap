# Copyright 2024 Stefan Hansson
# SPDX-License-Identifier: GPL-3.0-or-later

import sys

import pmb.helpers.pkgrel_bump
from pmb.helpers import logging


def pkgrel_bump(packages: list[str], dry_run: bool, auto: bool) -> None:
    would_bump = True

    if auto:
        would_bump = bool(pmb.helpers.pkgrel_bump.auto(dry_run))
    else:
        # Each package must exist
        for package in packages:
            pmb.helpers.pmaports.find(package)

        # Increase pkgrel
        for package in packages:
            pmb.helpers.pkgrel_bump.package(package, dry=dry_run)

    if dry_run and would_bump:
        logging.info("Pkgrels of package(s) would have been bumped!")
        sys.exit(1)
