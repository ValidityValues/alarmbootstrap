# Copyright 2026 Oliver Smith, Paul Adam
# SPDX-License-Identifier: GPL-3.0-or-later

import pmb.build
from pmb.core import Chroot


def build_init(chroot: Chroot) -> None:
    pmb.build.init(chroot)
