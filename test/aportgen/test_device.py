# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from pmb.aportgen.device import generate_deviceinfo_fastboot_content
from pmb.types import Bootimg

# Test case name -> (input, expected substrings, !expected substrings)
test_data: dict[str, tuple[Bootimg | None, list[str], list[str]]] = {
    "none": (None, ['kernel_cmdline=""', 'flash_pagesize="2048"'], []),
    "header_v0": (
        Bootimg(
            cmdline="beep boop",
            header_version=0,
            bootimg_qcdt="false",
            base="0x80000000",
            kernel_offset="0x8000",
            tags_offset="0x100",
            bootimg_qcdt_type=None,
            bootimg_qcdt_exynos_platform=None,
            bootimg_qcdt_exynos_subtype=None,
            dtb_offset=None,
            dtb_second="",
            pagesize="2048",
            ramdisk_offset="",
            second_offset="",
            mtk_label_kernel="",
            mtk_label_ramdisk="",
        ),
        [
            'kernel_cmdline="beep boop"',
            'flash_pagesize="2048"',
            'flash_offset_base="0x80000000"',
            'flash_offset_kernel="0x8000"',
            'flash_offset_tags="0x100"',
        ],
        [],
    ),
    "header_v2": (
        Bootimg(
            cmdline="console=ttyMSM0,115200n8",
            header_version=2,
            bootimg_qcdt="false",
            base="0x80000000",
            kernel_offset="",
            tags_offset="",
            bootimg_qcdt_type=None,
            bootimg_qcdt_exynos_platform=None,
            bootimg_qcdt_exynos_subtype=None,
            dtb_offset="0x101f00000",
            dtb_second="",
            pagesize="2048",
            ramdisk_offset="",
            second_offset="",
            mtk_label_kernel="",
            mtk_label_ramdisk="",
        ),
        [
            'kernel_cmdline="console=ttyMSM0,115200n8"',
            'flash_pagesize="2048"',
            'append_dtb="false"',
            'flash_offset_dtb="0x101f00000"',
        ],
        [],
    ),
    "header_v3": (
        Bootimg(
            cmdline="console=ttyMSM0,115200n8",
            header_version=3,
            bootimg_qcdt="false",
            base="",
            kernel_offset="",
            tags_offset="",
            bootimg_qcdt_type=None,
            bootimg_qcdt_exynos_platform=None,
            bootimg_qcdt_exynos_subtype=None,
            dtb_offset="",
            dtb_second="",
            pagesize="4096",
            ramdisk_offset="",
            second_offset="",
            mtk_label_kernel="",
            mtk_label_ramdisk="",
        ),
        [
            'kernel_cmdline="console=ttyMSM0,115200n8"',
            'flash_pagesize="4096"',
        ],
        [
            "flash_offset_base",
        ],
    ),
    "header_exynos_qcdt": (
        Bootimg(
            cmdline="console=ttySAC1,115200",
            header_version=2,
            bootimg_qcdt="true",
            base="",
            kernel_offset="",
            tags_offset="",
            bootimg_qcdt_type="exynos",
            bootimg_qcdt_exynos_platform="",
            bootimg_qcdt_exynos_subtype="",
            dtb_offset="",
            dtb_second="",
            pagesize="2048",
            ramdisk_offset="",
            second_offset="",
            mtk_label_kernel="",
            mtk_label_ramdisk="",
        ),
        [
            'kernel_cmdline="console=ttySAC1,115200"',
            'bootimg_qcdt="true"',
            'bootimg_qcdt_type="exynos"',
        ],
        [
            "bootimg_qcdt_exynos_platform",
            "bootimg_qcdt_exynos_subtype",
        ],
    ),
    "header_exynos_custom_qcdt": (
        Bootimg(
            cmdline="console=ttySAC1,115200",
            header_version=2,
            bootimg_qcdt="true",
            base="",
            kernel_offset="",
            tags_offset="",
            bootimg_qcdt_type="exynos",
            bootimg_qcdt_exynos_platform="0x347e",
            bootimg_qcdt_exynos_subtype="0x88668650",
            dtb_offset="",
            dtb_second="",
            pagesize="2048",
            ramdisk_offset="",
            second_offset="",
            mtk_label_kernel="",
            mtk_label_ramdisk="",
        ),
        [
            'kernel_cmdline="console=ttySAC1,115200"',
            'bootimg_qcdt="true"',
            'bootimg_qcdt_type="exynos"',
            'bootimg_qcdt_exynos_platform="0x347e"',
            'bootimg_qcdt_exynos_subtype="0x88668650"',
        ],
        [],
    ),
}


@pytest.mark.parametrize("case", [*test_data.keys()])
def test_deviceinfo_fastboot(case: str) -> None:
    bootimg = test_data[case][0]
    expected_substrings = test_data[case][1]
    unexpected_substrings = test_data[case][2]
    content = generate_deviceinfo_fastboot_content(bootimg)

    print(content)
    for substring in expected_substrings:
        assert substring in content, f"Expected substring not found: {substring}"

    for substring in unexpected_substrings:
        assert substring not in content, f"Unexpected substring found: {substring}"
