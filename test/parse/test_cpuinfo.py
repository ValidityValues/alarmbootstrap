# Copyright 2025 Stefan Hansson
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from typing import Final

from pmb.parse.cpuinfo import arm_big_little_first_group_ncpus

TESTDIR: Final[Path] = Path(__file__).parent.parent / "data/tests"


def test_arm_big_little_first_group_ncpus() -> None:
    ncpus = arm_big_little_first_group_ncpus()

    # Whether it is None or an int will depend on the host architecture, so let's allow any
    # reasonable value.
    assert ncpus is None or ncpus > 0


def test_google_grouper_tegra3_cpuinfo() -> None:
    assert arm_big_little_first_group_ncpus(TESTDIR / "cpuinfo-google-grouper-tegra3.txt") is None


def test_google_kukui_krane_mt8183_cpuinfo() -> None:
    assert arm_big_little_first_group_ncpus(TESTDIR / "cpuinfo-google-kukui-krane-mt8183.txt") == 4


def test_oneplus_echilada_sdm845_cpuinfo() -> None:
    assert arm_big_little_first_group_ncpus(TESTDIR / "cpuinfo-oneplus-enchilada-sdm845.txt") == 4


def test_x86_64_cpuinfo() -> None:
    assert arm_big_little_first_group_ncpus(TESTDIR / "cpuinfo-x86-64-desktop.txt") is None
