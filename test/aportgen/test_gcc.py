# Copyright 2025 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from _pytest.monkeypatch import MonkeyPatch

import pmb.helpers.repo
import pmb.parse.apkindex
from pmb.aportgen.gcc import depends_for_sonames
from pmb.core.apk_package import ApkPackage
from pmb.core.arch import Arch


def new_dummy_apkindex_block() -> ApkPackage:
    return ApkPackage(
        arch=Arch.x86_64,
        depends=[],
        origin=None,
        pkgname="Dummy",
        provides=[],
        provider_priority=None,
        timestamp=None,
        version="1.0.0",
    )


def test_depends_for_sonames(monkeypatch: MonkeyPatch) -> None:
    fake_apkindex: dict[str, dict[str, ApkPackage]] = {}
    arch_libc = Arch.x86_64
    libraries = {
        "so:libisl.so.*": "isl*",
        "so:libmpc.so.*": "mpc1",
    }

    def fake_apkindex_files(*args: object, **kwargs: object) -> str:
        return "fake/path/to/APKINDEX.tar.gz"

    def fake_apkindex_parse(*args: object, **kwargs: object) -> dict[str, dict[str, ApkPackage]]:
        print(fake_apkindex)
        return fake_apkindex

    monkeypatch.setattr(pmb.helpers.repo, "alpine_apkindex", fake_apkindex_files)
    monkeypatch.setattr(pmb.parse.apkindex, "parse", fake_apkindex_parse)

    # Empty apkindex -> can't find it
    with pytest.raises(RuntimeError) as e:
        depends_for_sonames(libraries, arch_libc)
    assert "not provided by any package" in str(e.value)

    # APKINDEX filled, the highest libisl.so must be picked
    fake_apkindex = {
        "so:libisl.so.23": {
            "isl25": new_dummy_apkindex_block(),
            "isl26": new_dummy_apkindex_block(),
        },
        "so:libisl.so.22": {
            "isl24": new_dummy_apkindex_block(),
        },
        "so:libmpc.so.3": {
            "mpc1": new_dummy_apkindex_block(),
        },
    }

    assert depends_for_sonames(libraries, arch_libc) == [
        "so:libisl.so.23",
        "so:libmpc.so.3",
    ]
