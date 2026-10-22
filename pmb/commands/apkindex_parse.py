# Copyright 2026 Oliver Smith, Paul Adam
# SPDX-License-Identifier: GPL-3.0-or-later
import json

import pmb.parse.apkindex
from pmb.core.apk_package import ApkPackageEncoder
from pmb.core.apkindex import Apkindex


def apkindex_parse(index: Apkindex, package: str | list[str]) -> None:
    result = pmb.parse.apkindex.parse(index)
    if package:
        if package not in result:
            raise RuntimeError(f"Package not found in the APKINDEX: {package}")
        print(json.dumps(result[package], indent=4, cls=ApkPackageEncoder))
    else:
        print(json.dumps(result, indent=4, cls=ApkPackageEncoder))
