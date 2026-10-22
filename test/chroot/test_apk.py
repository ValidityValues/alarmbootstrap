# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from _pytest.monkeypatch import MonkeyPatch

import pmb.chroot.apk
import pmb.config.pmaports
import pmb.helpers.apk
from pmb.chroot.apk import packages_get_locally_built_apks
from pmb.core.apk_package import ApkPackage
from pmb.core.arch import Arch
from pmb.core.context import get_context


@pytest.fixture
def apk_mocks(monkeypatch: MonkeyPatch) -> None:
    def _pmaports_config(_aports: None = None, _add_systemd_prefix: bool = True) -> dict:
        return {
            "channel": "edge",
            "supported_arches": "x86_64,aarch64,armv7,armhf",
        }

    monkeypatch.setattr(pmb.config.pmaports, "read_config", _pmaports_config)

    def _apkindex_package(
        _package: str,
        _arch: Arch,
        _must_exist: bool = False,
        indexes: None = None,
    ) -> ApkPackage | None:
        if _package == "package1":
            return ApkPackage(
                arch=_arch,
                depends=["package2"],
                origin=None,
                pkgname=_package,
                provides=[],
                provider_priority=None,
                timestamp=None,
                version="5.5-r0",
                pkgdesc="package1",
            )
        if _package == "package2":
            return ApkPackage(
                arch=_arch,
                depends=[],
                origin=None,
                pkgname=_package,
                provides=[],
                provider_priority=None,
                timestamp=None,
                version="5.5-r0",
                pkgdesc="package2",
            )
        if _package == "package3":
            return ApkPackage(
                arch=_arch,
                depends=["package1", "package4"],
                origin=None,
                pkgname=_package,
                provides=[],
                provider_priority=None,
                timestamp=None,
                version="5.5-r0",
                pkgdesc="package3",
            )
        # Test recursive dependency
        if _package == "package4":
            return ApkPackage(
                arch=_arch,
                depends=["package3"],
                origin=None,
                pkgname=_package,
                provides=[],
                provider_priority=None,
                timestamp=None,
                version="5.5-r0",
                pkgdesc="package4",
            )

        return None

    monkeypatch.setattr(pmb.parse.apkindex, "package", _apkindex_package)


def create_apk(pkgname: str, arch: Arch) -> Path:
    apk_file = get_context().config.work / "packages" / "edge" / arch / f"{pkgname}-5.5-r0.apk"
    apk_file.parent.mkdir(parents=True, exist_ok=True)
    apk_file.touch()
    return apk_file


def test_get_local_apks(pmb_args: None, apk_mocks: None) -> None:
    """Ensure packages_get_locally_built_apks() returns paths for local apks"""
    pkgname = "package1"
    arch = Arch.x86_64

    apk_file = create_apk(pkgname, arch)

    local = packages_get_locally_built_apks([pkgname, "fake-package"], arch)
    assert len(local) == 1
    assert "package1" in local
    assert local["package1"].parts[-2:] == apk_file.parts[-2:]

    create_apk("package2", arch)
    create_apk("package3", arch)
    create_apk("package4", arch)

    # Test recursive dependencies
    local = packages_get_locally_built_apks(["package3"], arch)
    assert len(local) == 4
    assert set(local.keys()) == {"package1", "package2", "package3", "package4"}


def test_install_run_apk_provider_conflict(
    pmb_args: None, apk_mocks: None, monkeypatch: MonkeyPatch
) -> None:
    """
    Test that locally built packages that provide a dependency should
    not be force-installed if apk resolved a different provider.
    https://gitlab.postmarketos.org/postmarketOS/pmbootstrap/-/issues/2734
    """
    from pmb.chroot.apk import install_run_apk

    arch = Arch.x86_64
    apk5 = create_apk("package5", arch)
    apk6 = create_apk("package6", arch)
    to_add_local = {"package5": apk5, "package6": apk6}

    # Simulate apk having resolved "virtual-pkg" to package6, not package5.
    monkeypatch.setattr(
        pmb.chroot.apk,
        "installed",
        lambda _chroot: {
            "package6": ApkPackage(
                arch=arch,
                depends=[],
                origin=None,
                pkgname="package6",
                provides=["virtual-pkg"],
                provider_priority=None,
                timestamp=None,
                version="5.5-r0",
                pkgdesc="package6",
            ),
            # provides alias also points to package6
            "virtual-pkg": ApkPackage(
                arch=arch,
                depends=[],
                origin=None,
                pkgname="package6",
                provides=["virtual-pkg"],
                provider_priority=None,
                timestamp=None,
                version="5.5-r0",
                pkgdesc="virtual-pkg",
            ),
        },
    )

    run_calls: list[list] = []
    monkeypatch.setattr(
        pmb.helpers.apk, "run", lambda cmd, _chroot, **_kwargs: run_calls.append(list(cmd))
    )

    chroot = MagicMock()
    chroot.is_mounted.return_value = True
    chroot.arch = arch

    install_run_apk(["some-package"], to_add_local, [], chroot)

    # the upgrade command should only contain package6, not package5
    virtual_cmds = [cmd for cmd in run_calls if "--virtual" in cmd]
    assert len(virtual_cmds) == 1
    cmd = virtual_cmds[0]
    assert not any("package5" in str(p) for p in cmd), (
        "package5 should have been filtered out (not installed by apk)"
    )
    assert any("package6" in str(p) for p in cmd), "package6 should be upgraded (apk installed it)"
