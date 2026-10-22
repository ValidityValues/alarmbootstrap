# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import time

import pmb.helpers.repo
import pmb.parse.apkindex
from pmb.core.arch import Arch
from pmb.helpers import logging

"""Various internal test commands for performance testing and debugging."""


def apkindex_parse_all() -> None:
    indexes = pmb.helpers.repo.apkindex_files(Arch.native())

    pkgs = 0
    indxs = len(indexes)
    start = time.time()
    for index in indexes:
        ret = pmb.parse.apkindex.parse(index)
        pkgs += len(ret)
    end = time.time()
    logging.info(f"Parsed {pkgs} packages from {indxs} APKINDEX files in {end - start:.3f} seconds")


def test(action: str) -> None:
    if action == "apkindex_parse_all":
        apkindex_parse_all()
