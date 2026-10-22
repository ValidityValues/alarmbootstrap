# Copyright 2025 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import glob
import logging
import os
from pathlib import Path

import pmb.build
import pmb.helpers.package
import pmb.helpers.pmaports
from pmb.core.arch import Arch
from pmb.core.pkgrepo import pkgrepo_paths
from pmb.helpers.devices import DeviceCategory, get_device_category_by_apkbuild_path
from pmb.meta import Cache
from pmb.types import WithExtraRepos


@Cache("repo")
def is_abuild_forked(repo: str | None) -> bool:
    """Check if abuild is forked to make sure we build it first (pmb#2401)"""
    with_extra_repos: WithExtraRepos

    if repo == "systemd":
        with_extra_repos = WithExtraRepos.ENABLED
    elif repo is None:
        with_extra_repos = WithExtraRepos.DISABLED
    else:
        raise RuntimeError(f"Unexpected repo value: {repo}")

    return bool(pmb.helpers.pmaports.find("abuild", False, False, with_extra_repos))


def generate(arch: Arch) -> list[dict[str, list[str] | str | None]]:
    """
    Get packages that need to be built, with all their dependencies. Include
       packages from extra-repos, no matter if systemd is enabled or not. This
       is used by bpo to fill its package database.

    :param arch: architecture (e.g. "armhf")
    :returns: a list like the following:
        [{"pkgname": "hello-world", "repo": None, "version": "1-r4"},
        {"pkgname": "package-depending-on-hello-world", "version": "0.5-r0", "repo": None}]
    """
    ret = []

    for pmaports_dir in pkgrepo_paths(WithExtraRepos.DISABLED):
        pattern = os.path.join(pmaports_dir, "**/*/APKBUILD")

        for apkbuild_path_str in glob.glob(pattern, recursive=True):
            apkbuild_path = Path(apkbuild_path_str)
            pkgname = apkbuild_path.parent.name
            package = pmb.parse.apkbuild(apkbuild_path)
            version = f"{package['pkgver']}-r{package['pkgrel']}"

            if arch not in Arch.from_arch_field(package["arch"]):
                continue

            relpath = apkbuild_path.relative_to(pmaports_dir)
            if (
                relpath.parts[0] == "device"
                and get_device_category_by_apkbuild_path(relpath) == DeviceCategory.ARCHIVED
            ):
                logging.debug(f"skipping archived device: {relpath}")
                continue

            repo = relpath.parts[1] if relpath.parts[0] == "extra-repos" else None

            depends = []
            dep_fields = ["depends", "makedepends", "checkdepends"]
            for dep_field in dep_fields:
                for dep in package[dep_field]:
                    if dep.startswith("!"):
                        continue

                    dep_data = pmb.helpers.package.get(dep, arch, must_exist=False)
                    if not dep_data:
                        logging.warning(f"WARNING: {pkgname}: failed to resolve dependency '{dep}'")
                        # Can't replace potential subpkgname
                        if dep != pkgname and dep not in depends:
                            depends += [dep]
                        continue
                    dep_pkgname = dep_data.pkgname
                    if dep_pkgname != pkgname and dep_pkgname not in depends:
                        depends += [dep_pkgname]

            # Add abuild to depends if needed
            if pkgname != "abuild" and is_abuild_forked(repo):
                depends = ["abuild", *depends]

            depends = sorted(depends)

            ret += [
                {
                    "pkgname": pkgname,
                    "repo": repo,
                    "version": version,
                    "depends": depends,
                }
            ]

    # "or -1" is needed for mypy
    # https://github.com/python/mypy/issues/9765#issuecomment-1238263745
    return sorted(ret, key=lambda d: d.get("pkgname") or -1)
