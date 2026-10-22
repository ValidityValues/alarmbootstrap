# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from pmb.parse.bootimg import bootimg as parse_bootimg
from pmb.types import Bootimg

"""
This is the result of compiling a totally empty devicetree file:
$ cat <<EOF | dtc -I dts -O dtb -o /tmp/empty.dtb
/dts-v1/;

/ {};
EOF

Then convert to python bytes:
$ python -c 'print(open("/tmp/empty.dtb", "rb").read())'
"""
empty_dtb = b"\xd0\r\xfe\xed\x00\x00\x00H\x00\x00\x008\x00\x00\x00H\x00\x00\x00(\x00\x00\x00\x11\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\t"


@pytest.fixture
def progs() -> dict[str, str]:
    progs: dict[str, str] = {
        # We expect the modern python version of mkbootimg from android-tools
        "mkbootimg": "",
    }
    for k in progs:
        v = shutil.which(k)
        if v is None:
            pytest.skip(f"{k} not found")
        else:
            progs[k] = v

    return progs


@pytest.fixture
def bootimg(progs: dict[str, str], tmp_path: Path) -> Callable:
    path: Path = tmp_path / "boot.img"
    cmd = [
        progs["mkbootimg"],
        "--kernel",
        "/dev/null",
        "--ramdisk",
        "/dev/null",
        "--output",
        str(path),
    ]

    def with_args(**kwargs: dict) -> Path:
        # Header version 2 requires a dtb file, be helpful and add one if it's missing
        if kwargs.get("header_version", 0) == 2 and "dtb" not in kwargs:
            path.with_suffix(".dtb").write_bytes(empty_dtb)
            cmd.extend(["--dtb", str(path.with_suffix(".dtb"))])
        for key, value in kwargs.items():
            cmd.extend([f"--{key}", str(value)])
        subprocess.run(cmd, check=True)
        return tmp_path / "boot.img"

    return with_args


# Due to limitations in the test infrastructure (somehow we have to clone
# all of pmaports for this!!) we stuff all the tests into one
def test_bootimg(bootimg: Callable, pmb_args: None, pmaports: None) -> None:
    bootimg_path = bootimg(base=0x80000000)

    # Header v0
    img: Bootimg = parse_bootimg(bootimg_path)
    print(f"Header v0: {img}")
    assert img["header_version"] == 0, "header v0 expected header version 0"
    assert img["cmdline"] == "", "header v0 expected empty cmdline"
    assert img["bootimg_qcdt"] == "false", "header v0 expected qcdt false"
    assert img["base"] == "0x80000000", "header v0 expected base 0x80000000"
    assert int(img["kernel_offset"], 16) == 0x8000, "header v0 expected kernel offset 0x8000"
    assert int(img["tags_offset"], 16) == 0x100, "header v0 expected tags offset 0x100"

    # Header v2
    bootimg_path = bootimg(base=0x80000000, header_version=2)

    img = parse_bootimg(bootimg_path)
    print(f"Header v2: {img}")
    assert img["header_version"] == 2, "header v2 expected header version 2"
    assert img["cmdline"] == "", "header v2 expected empty cmdline"
    assert img["bootimg_qcdt"] == "false", "header v2 expected qcdt false"
    assert img["base"] == "0x80000000", "header v2 expected base 0x80000000"
    assert int(img["kernel_offset"], 16) == 0x8000, "header v2 expected kernel offset 0x8000"
    assert int(img["tags_offset"], 16) == 0x100, "header v2 expected tags offset 0x100"
    assert img["dtb_offset"] is not None, "header v2 expected dtb offset"
    assert int(img["dtb_offset"], 16) == 0x101F00000, "header v2 expected dtb offset 0x101f00000"
    assert img["dtb_second"] == "", "header v2 expected dtb second empty"
    assert img["pagesize"] == "2048", "header v2 expected pagesize 2048"

    # Header v3, plus cmdline for fun
    bootimg_path = bootimg(header_version=3, cmdline="bleep boop console=ttyMSM0,115200n8")

    img = parse_bootimg(bootimg_path)
    print(f"Header v3: {img}")
    assert img["header_version"] == 3, "header v3 expected header version 3"
    assert img["cmdline"] == "bleep boop console=ttyMSM0,115200n8", "header v3 expected cmdline"
    assert img["kernel_offset"] == "", "header v3 expected empty kernel offset"
    assert img["pagesize"] == "4096", "header v3 expected pagesize 4096"
    assert img["ramdisk_offset"] == "", "header v3 expected empty ramdisk offset"


def test_bootimg_deviceinfo() -> None:
    # Test the deviceinfo file
    pass
