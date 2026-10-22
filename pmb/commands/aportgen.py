# Copyright 2024 Stefan Hansson
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import pmb.aportgen
from pmb.helpers import logging


def aportgen(package_list: list[str], fork_alpine: bool, fork_alpine_retain_branch: bool) -> None:
    for package in package_list:
        logging.info(f"Generate aport: {package}")
        pmb.aportgen.generate(package, fork_alpine, fork_alpine_retain_branch)
