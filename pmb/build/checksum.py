# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path

import pmb.build
import pmb.chroot
import pmb.helpers.pmaports
import pmb.helpers.run
from pmb.core import Chroot
from pmb.helpers import logging


def update(pkgname: str) -> None:
    """Fetch all sources and update the checksums in the APKBUILD."""
    pmb.build.init_abuild_minimal()
    pmb.build.copy_to_buildpath(pkgname, no_override=True)
    logging.info("(native) generate checksums for " + pkgname)
    pmb.chroot.user(["abuild", "checksum"], working_dir=Path("/home/pmos/build"))

    # Copy modified APKBUILD back
    source = Chroot.native() / "home/pmos/build/APKBUILD"
    target = f"{os.fspath(pmb.helpers.pmaports.find(pkgname))}/"
    pmb.helpers.run.user(["cp", source, target])


def verify(pkgname: str) -> None:
    """Fetch all sources and verify their checksums."""
    pmb.build.init_abuild_minimal()
    pmb.build.copy_to_buildpath(pkgname, no_override=True)
    logging.info("(native) verify checksums for " + pkgname)

    # Fetch and verify sources, "fetch" alone does not verify them:
    # https://github.com/alpinelinux/abuild/pull/86
    pmb.chroot.user(["abuild", "fetch", "verify"], working_dir=Path("/home/pmos/build"))
