# Copyright 2025 Stefan Hansson
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

import pytest

from pmb.helpers.devices import DeviceCategory, get_device_category_by_apkbuild_path


def test_get_device_category_by_apkbuild_path() -> None:
    valid_path_1 = Path("device") / "community" / "device-samsung-m0" / "APKBUILD"
    valid_path_2 = Path("pmos_work") / "device" / "main" / "device-pine64-pinephone" / "APKBUILD"

    # Missing category segment of path.
    invalid_path_1 = Path("APKBUILD")
    # Nonexistent category ("pendeltåg").
    invalid_path_2 = Path("device") / "pendeltåg" / "device-samsung-m0" / "APKBUILD"

    assert get_device_category_by_apkbuild_path(valid_path_1) == DeviceCategory.COMMUNITY
    assert get_device_category_by_apkbuild_path(valid_path_2) == DeviceCategory.MAIN

    with pytest.raises(RuntimeError):
        get_device_category_by_apkbuild_path(invalid_path_1)
    with pytest.raises(RuntimeError):
        get_device_category_by_apkbuild_path(invalid_path_2)
