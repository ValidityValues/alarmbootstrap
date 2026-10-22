# Copyright 2025 Oliver Smith
# Copyright 2026 Pablo Correa Gomez
# SPDX-License-Identifier: GPL-3.0-or-later

from _pytest.monkeypatch import MonkeyPatch

import pmb.helpers.package
from pmb.core.apk_package import ApkPackage
from pmb.core.arch import Arch
from pmb.helpers.package import check_version_constraints, depends_recurse, remove_operators


def test_remove_operators() -> None:
    assert remove_operators("soc-qcom") == "soc-qcom"
    assert remove_operators("soc-qcom>=0.34") == "soc-qcom"
    assert remove_operators("soc-qcom~1.3") == "soc-qcom"
    assert remove_operators("!soc-qcom") == "!soc-qcom"


def test_check_version_constraints() -> None:
    assert check_version_constraints("hello-world>=1.1", "1.0") is False
    assert check_version_constraints("hello-world>=1.0", "1.0") is True
    assert check_version_constraints("hello-world>=0.9", "1.0") is True

    assert check_version_constraints("hello-world>1.1", "1.0") is False
    assert check_version_constraints("hello-world>1.0", "1.0") is False
    assert check_version_constraints("hello-world>0.9", "1.0") is True

    assert check_version_constraints("hello-world<=1.1", "1.0") is True
    assert check_version_constraints("hello-world<=1.0", "1.0") is True
    assert check_version_constraints("hello-world<=0.9", "1.0") is False

    assert check_version_constraints("hello-world<1.1", "1.0") is True
    assert check_version_constraints("hello-world<1.0", "1.0") is False
    assert check_version_constraints("hello-world<0.9", "1.0") is False

    # Unexpected operator must always return True. We don't handle "=" and
    # operators with "~" (fuzzy matching) yet, so keep the existing behavior
    # for those and just install the pmaports package if there is one in that
    # case. This can be added later if we have a practical use case for it.
    assert check_version_constraints("hello-world♻️1.1", "1.0") is True
    assert check_version_constraints("hello-world♻️1.0", "1.0") is True
    assert check_version_constraints("hello-world♻️0.9", "1.0") is True


def test_depends_recurse_providers(monkeypatch: MonkeyPatch) -> None:
    def _get_package(pkgname: str, arch: Arch) -> ApkPackage:
        match pkgname:
            case pkgname if pkgname.startswith("so:libc.musl-"):
                return ApkPackage(
                    arch=arch,
                    depends=[],
                    pkgname="musl",
                    provides=[f"so:libc.musl-{arch}.so.1"],
                    version="1.2.5-r21",
                    origin=None,
                    provider_priority=None,
                    timestamp=None,
                    from_pmaports=False,
                )
            case "musl":
                return ApkPackage(
                    arch=arch,
                    depends=[],
                    pkgname="musl",
                    provides=[f"so:libc.musl-{arch}.so.1"],
                    version="1.2.5-r21",
                    origin=None,
                    provider_priority=None,
                    timestamp=None,
                    from_pmaports=False,
                )
            case "glib":
                return ApkPackage(
                    arch=arch,
                    depends=[f"so:libc.musl-{arch}.so.1"],
                    pkgname="glib",
                    provides=[],
                    version="2.31.1-r0",
                    origin=None,
                    provider_priority=None,
                    timestamp=None,
                    from_pmaports=False,
                )
            case "device-oneplus-fajita":
                return ApkPackage(
                    arch=arch,
                    depends=["glib"],
                    pkgname=pkgname,
                    provides=[],
                    version="34-r0",
                    origin=None,
                    provider_priority=None,
                    timestamp=None,
                    from_pmaports=True,
                )
            case _:
                raise AssertionError("This is unreachable code")

    monkeypatch.setattr(pmb.helpers.package, "get", _get_package)
    depends = depends_recurse("device-oneplus-fajita", Arch.aarch64)
    assert depends == ["device-oneplus-fajita", "glib", "musl"]


def test_depends_recurse_alternative_names(monkeypatch: MonkeyPatch) -> None:
    def _get_package(pkgname: str, arch: Arch) -> ApkPackage:
        match pkgname:
            case "dbus" | "dbus-dev<99990":
                return ApkPackage(
                    arch=arch,
                    depends=["dbus-libs"],
                    pkgname="dbus",
                    provides=[],
                    version="1.16.2-r0",
                    origin=None,
                    provider_priority=None,
                    timestamp=None,
                    from_pmaports=False,
                )
            case "dbus-libs":
                return ApkPackage(
                    arch=arch,
                    depends=["systemd-stage0-libs"],
                    pkgname="dbus",
                    provides=[],
                    version="99991.16.2-r0",
                    origin=None,
                    provider_priority=None,
                    timestamp=None,
                    from_pmaports=True,
                )
            case "systemd-stage0-libs" | "systemd-stage0":
                return ApkPackage(
                    arch=arch,
                    depends=["dbus-dev<99990"],
                    pkgname="systemd-stage0",
                    provides=[],
                    version="34-r0",
                    origin=None,
                    provider_priority=None,
                    timestamp=None,
                    from_pmaports=True,
                )
            case _:
                raise AssertionError("This is unreachable code")

    monkeypatch.setattr(pmb.helpers.package, "get", _get_package)
    depends = depends_recurse("systemd-stage0", Arch.aarch64)
    assert depends == ["dbus", "systemd-stage0"]
