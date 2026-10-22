# Copyright 2026 Oliver Smith, Paul Adam
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.build
from pmb.core.context import get_context


def newapkbuild(
    folder: str,
    pass_through: list[str],
    pkgname: str,
    pkgname_pkgver_srcurl: str,
) -> None:
    # Check for SRCURL usage
    is_url = False
    for prefix in ["http://", "https://", "ftp://"]:
        if pkgname_pkgver_srcurl.startswith(prefix):
            is_url = True
            break

    # Sanity check: -n is only allowed with SRCURL
    if pkgname and not is_url:
        raise RuntimeError(
            "You can only specify a pkgname (-n) when using SRCURL as last parameter."
        )

    pmb.build.newapkbuild(folder, pass_through, get_context().force)
