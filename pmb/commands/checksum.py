# Copyright 2026 Stefan Hansson, Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from collections.abc import Collection
from pathlib import Path

import pmb.build.checksum
from pmb.core import Chroot
from pmb.helpers import logging


def checksum(packages: Collection[str], do_changed: bool, do_verify: bool) -> None:
    def get_relevant_packages() -> Collection[str]:
        if do_changed:
            return pmb.helpers.git.get_changed_packages()
        elif packages:
            return packages
        else:
            return {Path.cwd().name}

    pmb.chroot.init(Chroot.native())

    packages = get_relevant_packages()

    for package in packages:
        if do_verify:
            pmb.build.checksum.verify(package)
        else:
            pmb.build.checksum.update(package)

    if not packages:
        # We should only ever reach this if the --changed argument is used as
        # otherwise at least one package must be specified in the arguments.
        logging.info("NOTE: No changed packages detected, not updating any checksums")
