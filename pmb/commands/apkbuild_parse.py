# Copyright 2026 Rakshit Kumar Singh, Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from collections.abc import Sequence

import pmb.helpers.pmaports


def apkbuild_parse(packages: Sequence[str]) -> None:
    # Default to all packages
    if not packages:
        packages = pmb.helpers.pmaports.get_list()

    # Iterate over all packages
    for package in packages:
        print(package + ":")
        aport = pmb.helpers.pmaports.find(package)
        print(json.dumps(pmb.parse.apkbuild(aport), indent=4, sort_keys=True))
