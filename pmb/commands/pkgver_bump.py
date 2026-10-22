# Copyright 2024 Stefan Hansson
# SPDX-License-Identifier: GPL-3.0-or-later

import pmb.helpers.pkgrel_bump


def pkgver_bump(packages: list[str]) -> None:
    # Each package must exist
    for package in packages:
        pmb.helpers.pmaports.find(package)

    for package in packages:
        pmb.helpers.pkgrel_bump.package(package, bump_type=pmb.helpers.pkgrel_bump.BumpType.PKGVER)
