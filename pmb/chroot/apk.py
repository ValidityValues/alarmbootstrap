# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import itertools
import os
import traceback
from collections.abc import Collection, Sequence
from pathlib import Path

import pmb.build
import pmb.chroot
import pmb.config
import pmb.helpers.apk
import pmb.parse.apkindex
from pmb.core import Chroot
from pmb.core.apkindex import Apkindex
from pmb.core.arch import Arch
from pmb.core.context import get_context
from pmb.helpers import logging
from pmb.helpers.exceptions import NonBugError
from pmb.meta import Cache
from pmb.types import PathString


@Cache("chroot")
def check_min_version(chroot: Chroot = Chroot.native()) -> None:
    """
    Check the minimum apk version, before running it the first time in the
    current session (lifetime of one pmbootstrap call).
    """
    # Skip if apk is not installed yet
    if not (chroot / "sbin/apk").exists():
        logging.debug(
            f"NOTE: Skipped apk version check for chroot '{chroot}'"
            ", because it is not installed yet!"
        )
        return

    installed_pkgs = installed(chroot)

    # Compare
    try:
        version_installed = installed_pkgs["apk-tools"].version
    except KeyError as exception:
        raise NonBugError(
            "ERROR: could not find apk-tools in chroot, run 'pmbootstrap zap' and try again"
        ) from exception

    try:
        pmb.helpers.apk.check_outdated(version_installed)
    except RuntimeError as exception:
        raise NonBugError(
            f"{exception}. Delete your http cache and zap all chroots, then try again: 'pmbootstrap zap -hc'"
        ) from exception


def packages_split_to_add_del(packages: Collection[str]) -> tuple[list[str], list[str]]:
    """
    Sort packages into "to_add" and "to_del" lists depending on their pkgname
    starting with an exclamation mark.

    :param packages: list of pkgnames
    :returns: (to_add, to_del) - tuple of lists of pkgnames, e.g.
              (["hello-world", ...], ["some-conflict-pkg", ...])
    """
    to_add = []
    to_del = []

    for package in packages:
        if package.startswith("!"):
            to_del.append(package.lstrip("!"))
        else:
            to_add.append(package)

    return (to_add, to_del)


def packages_get_locally_built_apks(package_list: Collection[str], arch: Arch) -> dict[str, Path]:
    """
    Iterate over packages and if existing, get paths to locally built packages.
    This is used to force apk to upgrade packages to newer local versions, even
    if the pkgver and pkgrel did not change.

    :param packages: list of pkgnames
    :param arch: architecture that the locally built packages should have
    :returns: a dict mapping pkgname to apk file path for each locally built
              package found, e.g.
              {"hello-world": Path("/mnt/pmbootstrap/packages/edge/x86_64/hello-world-1-r6.apk")}
    """
    channels: list[str] = pmb.config.pmaports.all_channels()
    local: dict[str, Path] = {}

    packages = set(package_list)

    walked: set[str] = set()
    while len(packages):
        package = packages.pop()
        data_repo = pmb.parse.apkindex.package(package, arch, False)
        if not data_repo:
            continue

        apk_file = f"{data_repo.pkgname}-{data_repo.version}.apk"
        # FIXME: we should know what channel we expect this package to be in
        # this will have weird behaviour if you build gnome-shell for edge and
        # then checkout out the systemd branch... But there isn't
        for channel in channels:
            apk_path = get_context().config.work / "packages" / channel / arch / apk_file
            if apk_path.exists():
                local[data_repo.pkgname] = apk_path
                break

        # Record all the packages we have visited so far
        walked |= {data_repo.pkgname, package}
        if data_repo.depends:
            # Add all dependencies to the list of packages to check, excluding
            # meta-deps like cmd:* and so:* as well as conflicts (!).
            packages |= (
                set(filter(lambda x: ":" not in x and "!" not in x, data_repo.depends)) - walked
            )

    return local


def install_run_apk(
    to_add: Collection[str], to_add_local: dict[str, Path], to_del: Collection[str], chroot: Chroot
) -> None:
    """
    Run apk to add packages, and ensure only the desired packages get
    explicitly marked as installed.

    :param to_add: list of pkgnames to install, without their dependencies
    :param to_add_local: return of packages_get_locally_built_apks()
    :param to_del: list of pkgnames to be deleted, this should be set to
                   conflicting dependencies in any of the packages to be
                   installed or their dependencies (e.g. ["unl0kr"])
    :param chroot: the chroot suffix, e.g. "native" or "rootfs_qemu-amd64"
    """
    # Sanitize packages: don't allow '--allow-untrusted' and other options
    # to be passed to apk!
    for package in itertools.chain(to_add, to_del):
        if package.startswith("-"):
            raise ValueError(f"Invalid package name: {package}")

    commands: list[Sequence[PathString]] = [["add", *to_add]]

    if to_del:
        commands += [["del", *to_del]]

    # There are still some edgecases where we manage to get here while the chroot is not
    # initialized. To not break the build, we initialize it here but print a big warning
    # and a stack trace so hopefully folks report it.
    if not chroot.is_mounted():
        logging.warning(f"({chroot}) chroot not initialized! This is a bug! Please report it.")
        logging.warning(f"({chroot}) initializing the chroot for you...")
        traceback.print_stack(file=logging.logfd)
        pmb.chroot.init(chroot)

    for i, command in enumerate(commands):
        # Ignore missing repos before initial build (bpo#137)
        if (
            os.getenv("PMB_APK_FORCE_MISSING_REPOSITORIES") == "1"
            or chroot.arch not in Arch.supported_binary()
        ):
            command = ["--force-missing-repositories", *command]

        # Virtual package related commands don't actually install or remove
        # packages, but only mark the right ones as explicitly installed.
        # So only display a progress bar for the "apk add" command which is
        # always the first one we process (i == 0).
        pmb.helpers.apk.run(command, chroot, with_progress=(i == 0))

    # Upgrade locally built packages to their local versions. This is done
    # after the main apk add so that apk has already resolved providers
    # correctly. This should only upgrade packages that apk actually installed.
    if to_add_local:
        installed_pkgs = installed(chroot)
        # Use pkg.pkgname rather than the dict keys, since the installed db
        # is indexed by both pkgname and all provides aliases. If we used the
        # provides alias, it would potentially result in a conflict (e.g.
        # installing eudev when systemd-udev is in the rootfs)
        installed_pkgnames = {pkg.pkgname for pkg in installed_pkgs.values()}
        local_add = [
            os.fspath(p) for pkgname, p in to_add_local.items() if pkgname in installed_pkgnames
        ]
        if local_add:
            # Use a virtual package to mark only the explicitly requested packages as
            # explicitly installed, not the ones in to_add_local
            command = ["add", "-u", "--virtual", ".pmbootstrap", *local_add]
            pmb.helpers.apk.run(command, chroot, with_progress=False)
            pmb.helpers.apk.run(["del", ".pmbootstrap"], chroot, with_progress=False)


def install(
    packages: Collection[str], chroot: Chroot, build: bool = True, quiet: bool = False
) -> None:
    """
    Install packages from pmbootstrap's local package index or the pmOS/Alpine
    binary package mirrors. Iterate over all dependencies recursively, and
    build missing packages as necessary.

    :param packages: list of pkgnames to be installed
    :param suffix: the chroot suffix, e.g. "native" or "rootfs_qemu-amd64"
    :param build: automatically build the package, when it does not exist yet
                  or needs to be updated, and it is inside pmaports. For the
                  special case that all packages are expected to be in Alpine's
                  repositories, set this to False for performance optimization.
    """
    arch = chroot.arch
    context = get_context()

    if not packages:
        logging.verbose("pmb.chroot.apk.install called with empty packages list, ignoring")
        return

    # Initialize chroot
    check_min_version(chroot)

    if any(p.startswith("!") for p in packages):
        msg = f"({chroot}) install: packages with '!' are not supported!\n{', '.join(packages)}"
        raise ValueError(msg)

    to_add, to_del = packages_split_to_add_del(packages)

    if build and context.config.build_pkgs_on_install:
        pmb.build.packages(context, to_add, arch)

    to_add_local = packages_get_locally_built_apks(to_add, arch)

    if not quiet:
        logging.info(f"({chroot}) install {' '.join(packages)}")
    install_run_apk(to_add, to_add_local, to_del, chroot)


def installed(suffix: Chroot = Chroot.native()) -> dict[str, pmb.core.apk_package.ApkPackage]:
    """
    Read the list of installed packages (which has almost the same format, as
    an APKINDEX, but with more keys).

    :returns: a dictionary with the following structure:
              { "postmarketos-mkinitfs": ApkPackage }

    """
    index = Apkindex.from_installed_db(suffix)
    try:
        return {block.pkgname: block for block in index.get_apk_packages()}
    except FileNotFoundError:
        logging.verbose(f"NOTE: installed db file does not exist for this architecture {index}")
        return {}
