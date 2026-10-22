# Copyright 2026 Pablo Correa Gomez
# SPDX-License-Identifier: GPL-3.0-or-later

from pmb.core.apkindex import Apkindex


def test_apkindex_parse_blocks(valid_apkindex_file: Apkindex) -> None:
    assert len(valid_apkindex_file.get_apk_packages()) == 14
