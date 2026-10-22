# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path

import pmb.build
import pmb.chroot
import pmb.helpers.cli
import pmb.parse
from pmb.core import Chroot
from pmb.core.pkgrepo import pkgrepo_default_path
from pmb.helpers import logging
from pmb.types import PathString


def newapkbuild(folder: PathString, args_passed: list[str], force: bool = False) -> None:
    # Initialize build environment and build folder
    pmb.build.init()
    pmb.chroot.init(Chroot.native())
    build = Path("/home/pmos/build")
    build_outside = Chroot.native() / build
    if build_outside.exists():
        pmb.chroot.root(["rm", "-r", build])
    pmb.chroot.user(["mkdir", "-p", build])

    # Run newapkbuild
    pmb.chroot.user(["newapkbuild", *args_passed], working_dir=build)
    glob_result = list(build_outside.glob("*/APKBUILD"))
    if not len(glob_result):
        return

    # Paths for copying
    source_apkbuild = glob_result[0]
    pkgname = pmb.parse.apkbuild(source_apkbuild, False)["pkgname"]
    target = pkgrepo_default_path() / folder / pkgname

    # Move /home/pmos/build/$pkgname/* to /home/pmos/build/*
    for path in build_outside.glob("*/*"):
        path_inside = build / pkgname / os.path.basename(path)
        pmb.chroot.user(["mv", path_inside, build])
    pmb.chroot.user(["rmdir", build / pkgname])

    # Overwrite confirmation
    if os.path.exists(target):
        logging.warning(f"WARNING: Folder already exists: {target}")
        question = "Continue and delete its contents?"
        if not force and not pmb.helpers.cli.confirm(question):
            raise RuntimeError("Aborted.")
        pmb.helpers.run.user(["rm", "-r", target])

    # Copy the aport (without the extracted src folder)
    logging.info(f"Create {target}")
    pmb.helpers.run.user(["mkdir", "-p", target])
    for path in build_outside.glob("*"):
        if not path.is_dir():
            pmb.helpers.run.user(["cp", path, target])
