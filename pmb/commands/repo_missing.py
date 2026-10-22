# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import json

import pmb.helpers.repo_missing
from pmb.core.arch import Arch


def repo_missing(arch: Arch | None) -> None:
    if arch is None:
        raise AssertionError
    missing = pmb.helpers.repo_missing.generate(arch)
    print(json.dumps(missing, indent=4))
