# Copyright 2026 Hugo Posnic
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.chroot.initfs


def initfs(action: str, hook: str | None) -> None:
    pmb.chroot.initfs.frontend(action, hook)
