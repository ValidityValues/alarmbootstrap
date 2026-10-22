# Copyright 2026 Pablo Correa Gomez
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from pmb.core.apk_package import ApkPackage
from pmb.core.arch import Arch


def test_apkindex_block_full() -> None:
    block = ApkPackage.from_apkindex_block(
        [
            "A:x86_64",
            "D:dep-a dep-b",
            "o:origin",
            "P:pkgname",
            "p:so:liba.so=1.0 virtual",
            "k:10",
            "t:111011",
            "T:this is a test package",
            "V:1.0.0-r0",
        ]
    )
    assert block.arch == Arch.x86_64
    assert block.depends == ["dep-a", "dep-b"]
    assert block.origin == "origin"
    assert block.pkgname == "pkgname"
    assert block.provides == ["so:liba.so", "virtual"]
    assert block.provider_priority == 10
    assert block.timestamp == "111011"
    assert block.version == "1.0.0-r0"
    assert block.pkgdesc == "this is a test package"


def test_apkindex_block_missing_optionals() -> None:
    block = ApkPackage.from_apkindex_block(
        [
            "A:x86_64",
            "D:dep-a dep-b",
            "P:pkgname",
            "p:so:liba.so=1.0 virtual",
            "k:10",
            "V:1.0.0-r0",
        ]
    )
    assert block.origin is None
    assert block.timestamp is None
    assert block.pkgdesc is None


def test_apkindex_block_bad_priority() -> None:
    with pytest.raises(RuntimeError):
        ApkPackage.from_apkindex_block(
            [
                "A:x86_64",
                "P:pkgname",
                "V:1.0.0-r0",
                "k:a20",
            ]
        )


def test_apkindex_block_missing_required() -> None:
    with pytest.raises(RuntimeError):
        ApkPackage.from_apkindex_block(
            [
                "A:x86_64",
                "V:1.0.0-r0",
            ]
        )


def test_apkindex_block_duplicated() -> None:
    with pytest.raises(RuntimeError):
        ApkPackage.from_apkindex_block(
            [
                "A:x86_64",
                "P:pkgname",
                "P:pkgnameother",
                "V:1.0.0-r0",
            ]
        )
