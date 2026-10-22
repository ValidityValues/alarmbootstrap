# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Functions that work with both pmaports and binary package repos.

See also:

    - pmb/helpers/pmaports.py (work with pmaports)

    - pmb/helpers/repo.py (work with binary package repos)
"""

from typing import overload

import pmb.helpers.pmaports
import pmb.helpers.repo
import pmb.parse.version
from pmb.core.apk_package import ApkPackage
from pmb.core.arch import Arch
from pmb.helpers import logging
from pmb.meta import Cache


def remove_operators(package: str) -> str:
    for operator in [">", ">=", "<=", "=", "<", "~"]:
        if operator in package:
            package = package.split(operator, maxsplit=1)[0]
            break
    return package


def check_version_constraints(pkgname_with_op: str, version: str) -> bool:
    # Operators and matching return values from pmb.parse.version.compare()
    operators = {
        ">=": [0, 1],
        ">": [1],
        "<=": [-1, 0],
        "<": [-1],
    }

    for op, valid_results in operators.items():
        if op not in pkgname_with_op:
            continue
        ver_req = pkgname_with_op.split(op, 1)[1]
        result = pmb.parse.version.compare(version, ver_req)
        logging.verbose(
            f"check_version_constraints: op:{op}, version:{version}, ver_req:{ver_req}, result:{result}"
        )
        if result in valid_results:
            logging.verbose(f"{pkgname_with_op}: matches package")
            return True
        else:
            logging.verbose(f"{pkgname_with_op}: does not match package")
            return False

    logging.verbose(f"check_version_constraints: ignoring {pkgname_with_op}")
    return True


@overload
def get(pkgname: str, arch: Arch) -> ApkPackage: ...


@overload
def get(pkgname: str, arch: Arch, must_exist: bool = ...) -> ApkPackage | None: ...


@Cache("pkgname", "arch")
def get(
    pkgname: str,
    arch: Arch,
    must_exist: bool = True,
) -> ApkPackage | None:
    """
    Find a package in pmaports, and as fallback in the APKINDEXes of the binary packages.

    :param pkgname: package name (e.g. "hello-world")
    :param arch: architecture of the binary package.
    :param must_exist: raise an exception, if not found

    :returns: * data from the parsed APKBUILD or APKINDEX in the following format:
                    {"arch": ["noarch"], "depends": ["busybox-extras", "lddtree", ...],
                    "pkgname": "postmarketos-mkinitfs", "provides": ["mkinitfs=0..1"],
                    "version": "0.0.4-r10"}

        * None if the package was not found
    """
    # Find in pmaports
    pmaport = pmb.helpers.pmaports.get(pkgname, False)
    if pmaport and arch in Arch.from_arch_field(pmaport["arch"]):
        return ApkPackage.from_apkbuild(pmaport, arch)

    # Find in APKINDEX
    pmb.helpers.repo.update(arch)
    ret_repo = pmb.parse.apkindex.package(pkgname, arch, False)
    if ret_repo:
        return ret_repo

    # Could not find the package
    if not must_exist:
        return None
    raise RuntimeError(f"Package '{pkgname}': Could not find it in pmaports or any APKINDEX!")


@Cache("pkgname", "arch")
def depends_recurse(pkgname: str, arch: Arch) -> list[str]:
    """
    Recursively resolve all of the package's dependencies.

    :param pkgname: name of the package (e.g. "device-samsung-i9100")
    :param arch: preferred architecture for binary packages
    :returns: a list of pkgname_start and all its dependencies, e.g:
        ["busybox-static-armhf", "device-samsung-i9100",
        "linux-samsung-i9100", ...]
    """
    # Build ret (by iterating over the queue)
    queue = {pkgname}
    ret: set[str] = set()
    alternative_names: set[str] = set()
    while len(queue):
        pkgname = queue.pop()
        package = get(pkgname, arch)

        # Add its depends to the queue
        for depend in package.depends:
            if depend not in ret and depend not in alternative_names:
                queue.add(depend)

        # Add the pkgname (not possible subpkgname) to ret
        ret.add(package.pkgname)
        alternative_names.update(package.provides)
        alternative_names.add(pkgname)

    return sorted(ret)
