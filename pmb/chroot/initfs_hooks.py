# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.chroot.apk
import pmb.config
import pmb.parse._apkbuild
from pmb.core import Chroot
from pmb.core.pkgrepo import pkgrepo_glob_one, pkgrepo_iglob
from pmb.helpers import logging
from pmb.helpers.exceptions import NonBugError


def _list_chroot(suffix: Chroot, remove_prefix: bool = True) -> list[str]:
    ret = []
    prefix = pmb.config.initfs_hook_prefix
    for pkgname in pmb.chroot.apk.installed(suffix):
        if pkgname.startswith(prefix):
            if remove_prefix:
                ret.append(pkgname[len(prefix) :])
            else:
                ret.append(pkgname)
    return ret


def _list_hook_packages() -> dict[str, str]:
    pkgs = {}
    pmaports_cfg = pmb.config.pmaports.read_config()
    # This can be removed once all pmaports stable releases use merged hooks
    # Likely after v26.12 is EOL
    if pmaports_cfg.get("supported_merged_mkinitfs_hooks", False):
        pkg_dir = pkgrepo_glob_one("main/postmarketos-mkinitfs-hook")
        if pkg_dir is None:
            raise RuntimeError("No postmarketos-mkinitfs-hook available")
        main_apkbuild = pmb.parse.apkbuild(pkg_dir / "APKBUILD")
        for subpackage, info in main_apkbuild["subpackages"].items():
            if not subpackage.startswith(pmb.config.initfs_hook_prefix):
                continue
            pkgs[subpackage.removeprefix(pmb.config.initfs_hook_prefix)] = info["pkgdesc"]
    else:
        packages = pkgrepo_iglob(f"*/{pmb.config.initfs_hook_prefix}*")
        for p in packages:
            hook_desc = pmb.parse._apkbuild.apkbuild(p)["pkgdesc"]
            pkgs[p.name.removeprefix(pmb.config.initfs_hook_prefix)] = hook_desc
    return pkgs


def ls(suffix: Chroot) -> None:
    hooks_chroot = _list_chroot(suffix)

    for hook, desc in _list_hook_packages().items():
        line = f"* {hook}: {desc} ({'' if hook in hooks_chroot else 'not '}installed)"
        logging.info(line)


def add(hook: str, suffix: Chroot) -> None:
    if hook not in _list_hook_packages():
        raise NonBugError(
            "Invalid hook name! Run 'pmbootstrap initfs hook_ls' to get a list of all hooks."
        )
    prefix = pmb.config.initfs_hook_prefix
    pmb.chroot.apk.install([f"{prefix}{hook}"], suffix)


def delete(hook: str, suffix: Chroot) -> None:
    if hook not in _list_chroot(suffix):
        raise NonBugError("There is no such hook installed!")
    prefix = pmb.config.initfs_hook_prefix
    pmb.helpers.apk.run(["del", f"{prefix}{hook}"], suffix)


def update(suffix: Chroot) -> None:
    """Rebuild and update all hooks that are out of date"""
    pmb.chroot.apk.install(_list_chroot(suffix, False), suffix)
