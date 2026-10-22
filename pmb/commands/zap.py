# Copyright 2026 Stefan Hansson, Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.chroot


def zap(
    dry: bool,
    http: bool,
    distfiles: bool,
    pkgs_local: bool,
    pkgs_local_mismatch: bool,
    pkgs_online_mismatch: bool,
    rust: bool,
    netboot: bool,
) -> None:
    pmb.chroot.zap(
        dry=dry,
        http=http,
        distfiles=distfiles,
        pkgs_local=pkgs_local,
        pkgs_local_mismatch=pkgs_local_mismatch,
        pkgs_online_mismatch=pkgs_online_mismatch,
        rust=rust,
        netboot=netboot,
    )

    # Don't write the "Done" message
    pmb.helpers.logging.disable()
