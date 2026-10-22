# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import pmb.chroot


def shutdown() -> None:
    pmb.chroot.shutdown()
