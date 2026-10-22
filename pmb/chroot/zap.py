# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import glob
import os
from pathlib import Path

import pmb.build.other
import pmb.chroot
import pmb.config.pmaports
import pmb.config.workdir
import pmb.helpers.apk
import pmb.helpers.cli
import pmb.helpers.mount
import pmb.helpers.pmaports
import pmb.helpers.run
import pmb.parse.apkindex
from pmb.core import Chroot
from pmb.core.apkindex import Apkindex
from pmb.core.arch import Arch
from pmb.core.context import get_context
from pmb.helpers import logging
from pmb.helpers.exceptions import CommandFailedError, NonBugError


def del_chroot(path: Path, confirm: bool = True, dry: bool = False) -> None:
    if confirm and not pmb.helpers.cli.confirm(f"Remove {path}?"):
        return
    if dry:
        return

    # Safety first!
    if not path.is_absolute():
        raise ValueError("Path must be absolute")
    if not path.is_relative_to(get_context().config.work):
        raise ValueError("Path must be relative to pmbootstrap's work directory")

    # umount_all() will throw if any mount under path fails to unmount
    pmb.helpers.mount.umount_all(path)

    pmb.helpers.run.root(["rm", "-rf", path])


def zap_buildroots() -> None:
    """
    Shutdown everything inside the chroots used for package builds, umount
    everything and then delete the chroots from the work-directory.
    """
    pmb.chroot.shutdown(only_build_related=True)
    for root in Chroot.glob():
        if root.name == "chroot_native" or root.name.startswith("chroot_buildroot"):
            del_chroot(root, False, False)
    pmb.chroot.init.cache_clear()


def zap(
    confirm: bool = True,
    dry: bool = False,
    pkgs_local: bool = False,
    http: bool = False,
    pkgs_local_mismatch: bool = False,
    pkgs_online_mismatch: bool = False,
    distfiles: bool = False,
    rust: bool = False,
    netboot: bool = False,
) -> None:
    """
    Shutdown everything inside the chroots (e.g. adb), umount
    everything and then safely remove folders from the work-directory.

    :param dry: Only show what would be deleted, do not delete for real
    :param pkgs_local: Remove *all* self-compiled packages (!)
    :param http: Clear the http cache (used e.g. for the initial apk download)
    :param pkgs_local_mismatch: Remove the packages that have
        a different version compared to what is in the aports folder.
    :param pkgs_online_mismatch: Clean out outdated binary packages
        downloaded from mirrors (e.g. from Alpine)
    :param distfiles: Clear the downloaded files cache
    :param rust: Remove rust related caches
    :param netboot: Remove images for netboot

    NOTE: This function gets called in pmb/config/init.py, with only get_context().config.work
    and args.device set!
    """
    # Delete packages with a different version compared to aports,
    # then re-index
    if pkgs_local_mismatch:
        zap_pkgs_local_mismatch(confirm, dry)

    # Delete outdated binary packages
    if pkgs_online_mismatch:
        zap_pkgs_online_mismatch(confirm, dry)

    try:
        pmb.chroot.shutdown()
    except CommandFailedError as exception:
        raise NonBugError(
            f"Failed to shut down all chroots. Ensure they're not doing any work and you're not chrooted into any. ({exception})"
        ) from exception

    # Deletion patterns for folders inside get_context().config.work
    patterns = []
    if pkgs_local:
        patterns += ["packages"]
    if http:
        patterns += ["cache_http"]
    if distfiles:
        patterns += ["cache_distfiles"]
    if rust:
        patterns += ["cache_rust"]
    if netboot:
        patterns += ["images_netboot"]

    for chroot in Chroot.glob():
        del_chroot(chroot, confirm, dry)

    # Delete everything matching the patterns
    for pattern in patterns:
        logging.debug(f"Deleting {pattern}")
        pattern = os.path.realpath(f"{get_context().config.work}/{pattern}")
        matches = glob.glob(pattern)
        for match in matches:
            if not confirm or pmb.helpers.cli.confirm(f"Remove {match}?"):
                logging.info(f"% rm -rf {match}")
                if not dry:
                    pmb.helpers.run.root(["rm", "-rf", match])

    # Remove config init dates for deleted chroots
    pmb.config.workdir.clean()

    # Let chroot.init be called again
    pmb.chroot.init.cache_clear()

    # Print amount of cleaned up space
    if dry:
        logging.info("Dry run: nothing has been deleted")


def zap_pkgs_local_mismatch(confirm: bool = True, dry: bool = False) -> None:
    channel = pmb.config.pmaports.read_config()["channel"]
    if not os.path.exists(f"{get_context().config.work}/packages/{channel}"):
        return

    question = (
        "Remove binary packages that are newer than the corresponding"
        f" pmaports (channel '{channel}')?"
    )
    if confirm and not pmb.helpers.cli.confirm(question):
        return

    reindex = False
    for apkindex in Apkindex.iter_package_indexes_for_channel(channel):
        # Delete packages without same version in aports
        for pkg in apkindex.get_apk_packages():
            # Apk path
            apk_path_short = f"{pkg.arch}/{pkg.pkgname}-{pkg.version}.apk"
            apk_path = f"{get_context().config.work}/packages/{channel}/{apk_path_short}"
            if not os.path.exists(apk_path):
                logging.info(f"WARNING: Package mentioned in index not found: {apk_path_short}")
                continue

            if pkg.origin is None:
                raise RuntimeError("Can't handle virtual packages")

            # Aport path
            aport_path = pmb.helpers.pmaports.find_optional(pkg.origin)
            if not aport_path:
                logging.info(f"% rm {apk_path_short} ({pkg.origin} aport not found)")
                if not dry:
                    pmb.helpers.run.root(["rm", apk_path])
                    reindex = True
                continue

            # Clear out any binary apks that do not match what is in aports
            apkbuild = pmb.parse.apkbuild(aport_path)
            version_aport = f"{apkbuild['pkgver']}-r{apkbuild['pkgrel']}"
            if pkg.version != version_aport:
                logging.info(f"% rm {apk_path_short} ({pkg.origin} aport: {version_aport})")
                if not dry:
                    pmb.helpers.run.root(["rm", apk_path])
                    reindex = True

    if reindex:
        pmb.build.other.index_repo()


def zap_pkgs_online_mismatch(confirm: bool = True, dry: bool = False) -> None:
    # Check whether we need to do anything
    paths = list(get_context().config.work.glob("cache_apk_*"))
    if not len(paths):
        return
    if confirm and not pmb.helpers.cli.confirm("Remove outdated binary packages?"):
        return

    # Iterate over existing apk caches
    clean_native = False
    for path in paths:
        arch = Arch.from_str(path.name.split("_", 2)[2])

        if not dry:
            if arch == Arch.native():
                clean_native = True
                continue
            pmb.helpers.apk.cache_clean(arch)

    # pmb#2672: With apkv3, APKINDEX files get deleted when running "apk cache
    # clean". This is unexpected and needs to be investigated. Meanwhile run
    # cache_clean() on the native arch last, as it needs the APKINDEX for the
    # Alpine main repo of the native arch (even if cleaning other arches) in
    # order to set up the chroot where we run "apk cache clean". This prevents
    # crashing in "pmbootstrap zap -a" and "pmbootstrap zap -o".
    if clean_native and not dry:
        pmb.helpers.apk.cache_clean(Arch.native())
