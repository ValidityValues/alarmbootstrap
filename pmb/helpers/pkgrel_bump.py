# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from enum import Enum
from typing import Any

import pmb.helpers.file
import pmb.helpers.pmaports
import pmb.helpers.repo
import pmb.parse
import pmb.parse.apkindex
from pmb.core.apk_package import ApkPackage
from pmb.core.arch import Arch
from pmb.helpers import logging


class BumpType(Enum):
    PKGREL = "pkgrel"
    PKGVER = "pkgver"


def package(
    pkgname: str, reason: str = "", dry: bool = False, bump_type: BumpType = BumpType.PKGREL
) -> None:
    """
    Increase the pkgrel or pkgver in the APKBUILD of a specific package.

    :param pkgname: name of the package
    :param reason: string to display as reason why it was increased
    :param dry: don't modify the APKBUILD, just print the message
    :param bump_type: whether to bump pkgrel or pkgver
    """
    # Current and new pkgrel or pkgver
    path = pmb.helpers.pmaports.find(pkgname) / "APKBUILD"
    apkbuild = pmb.parse.apkbuild(path)
    version = int(apkbuild[bump_type.value])
    version_new = version + 1

    # Display the message, bail out in dry mode
    logging.info(
        "Increase '"
        + pkgname
        + f"' {bump_type.value} ("
        + str(version)
        + " -> "
        + str(version_new)
        + ")"
        + reason
    )
    if dry:
        return

    # Increase
    old = f"\n{bump_type.value}=" + str(version) + "\n"
    new = f"\n{bump_type.value}=" + str(version_new) + "\n"
    pmb.helpers.file.replace(path, old, new)

    if bump_type == BumpType.PKGVER:
        pkgrel = int(apkbuild["pkgrel"])
        # Set pkgrel to 0 if we bump pkgver
        pmb.helpers.file.replace(path, f"pkgrel={pkgrel}", "pkgrel=0")

    # Verify
    pmb.parse.apkbuild.cache_clear()
    apkbuild = pmb.parse.apkbuild(path)
    if int(apkbuild[bump_type.value]) != version_new:
        raise RuntimeError(
            f"Failed to bump {bump_type.value} for package '{pkgname}'."
            " Make sure that there's a line with exactly the"
            f" string '{old.strip()}' and nothing else in: {path}"
        )


def auto_apkindex_package(
    arch: Arch, aport: dict[str, Any], apk: ApkPackage, dry: bool = False
) -> bool:
    """
    Bump the pkgrel of a specific package if it is outdated in the given APKINDEX.

    :param arch: the architecture, e.g. "armhf"
    :param aport: parsed APKBUILD of the binary package's origin:
                  {"pkgname": ..., "pkgver": ..., "pkgrel": ..., ...}
    :param apk: information about the binary package from the APKINDEX:
                {"version": ..., "depends": [...], ...}
    :param dry: don't modify the APKBUILD, just print the message
    :returns: True when there was an APKBUILD that needed to be changed.
    """
    version_aport = aport["pkgver"] + "-r" + aport["pkgrel"]
    version_apk = apk.version
    pkgname = aport["pkgname"]

    # Skip when aport version != binary package version
    compare = pmb.parse.version.compare(version_aport, version_apk)
    if compare == -1:
        logging.warning(
            f"{pkgname}: skipping, because the aport version {version_aport} is lower"
            f" than the binary version {version_apk}"
        )
        return False
    if compare == 1:
        logging.verbose(
            f"{pkgname}: skipping, because the aport version {version_aport} is higher"
            f" than the binary version {version_apk}"
        )
        return False

    # Find missing depends
    logging.verbose("{}: checking depends: {}".format(pkgname, ", ".join(apk.depends)))
    missing = []
    indexes = pmb.helpers.repo.apkindex_files(arch)
    for depend in apk.depends:
        if depend.startswith("!"):
            # Ignore conflict-dependencies
            continue

        providers = pmb.parse.apkindex.providers(depend, indexes, must_exist=False)
        if providers == {} and (
            # We're only interested in missing depends starting with "so:"
            # (which means dynamic libraries that the package was linked
            # against) and packages for which no aport exists.
            depend.startswith("so:") or not pmb.helpers.pmaports.find_optional(depend)
        ):
            missing.append(depend)

    # Increase pkgrel
    if len(missing):
        package(pkgname, reason=", missing depend(s): " + ", ".join(missing), dry=dry)
        return True

    return False


def auto(dry: bool = False) -> list[str]:
    """:returns: list of aport names, where the pkgrel needed to be changed"""
    ret = []
    for arch in Arch.supported():
        paths = pmb.helpers.repo.apkindex_files(arch, exclude_mirrors=["alpine"])
        for path in paths:
            logging.info(f"scan {path}")
            index = pmb.parse.apkindex.parse(path, False)
            for pkgname, apk in index.items():
                origin = apk.origin
                # Only increase once!
                if origin in ret:
                    logging.verbose(f"{pkgname}: origin '{origin}' found again")
                    continue

                if origin is None:
                    logging.warning(f"{pkgname}: skipping, is a virtual package")
                    continue

                aport_path = pmb.helpers.pmaports.find_optional(origin)
                if not aport_path:
                    logging.warning(f"{pkgname}: origin '{origin}' aport not found")
                    continue
                aport = pmb.parse.apkbuild(aport_path)
                if auto_apkindex_package(arch, aport, apk, dry):
                    ret.append(pkgname)
    return ret
