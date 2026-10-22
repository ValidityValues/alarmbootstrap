# Copyright 2026 Oliver Smith, Paul Adam
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.chroot
import pmb.chroot.apk
from pmb.core import Chroot
from pmb.core.arch import Arch
from pmb.helpers import logging
from pmb.types import RunOutputTypeDefault


def stats(arch: Arch | None) -> None:
    # Chroot suffix
    chroot = Chroot.buildroot(arch or Arch.native())

    pmb.chroot.init(chroot)

    # Install ccache and display stats
    pmb.chroot.apk.install(["ccache"], chroot)
    logging.info(f"({chroot}) % ccache -s")
    pmb.chroot.user(["ccache", "-s"], chroot, output=RunOutputTypeDefault.STDOUT)
