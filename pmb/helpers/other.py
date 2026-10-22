# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import re
from pathlib import Path
from typing import Any

import pmb.chroot
import pmb.config
import pmb.helpers.pmaports
import pmb.helpers.run
from pmb.core.context import get_context
from pmb.core.pkgrepo import pkgrepo_default_path
from pmb.helpers import logging
from pmb.helpers.exceptions import NonBugError


def folder_size(path: Path) -> int:
    """
    Run `du` to calculate the size of a folder.

    (this is less code and faster than doing the same task in pure Python)
    This result is only approximately right, but good enough for pmbootstrap's use case (#760).

    :returns: folder size in kilobytes
    """
    output = pmb.helpers.run.root(["du", "-ks", path], output_return=True)

    # Only look at last line to filter out sudo garbage (#1766)
    last_line = output.split("\n")[-2]

    return int(last_line.split("\t")[0])


def check_grsec() -> None:
    """
    Check if the current kernel is based on the grsec patchset.

    Also check if the chroot_deny_chmod option is enabled.
    Raise an exception in that case, with a link to the issue. Otherwise, do nothing.
    """
    path = "/proc/sys/kernel/grsecurity/chroot_deny_chmod"
    if not os.path.exists(path):
        return

    raise RuntimeError(
        "You're running a kernel based on the grsec patchset. This is not supported."
    )


def check_binfmt_misc() -> None:
    """
    Check if the 'binfmt_misc' module is loaded.

    This is done by checking, if /proc/sys/fs/binfmt_misc/ exists.
    If it exists, then do nothing.
    Otherwise, load the module and mount binfmt_misc.
    If that fails as well, raise an exception pointing the user to the wiki.
    """
    path = "/proc/sys/fs/binfmt_misc/status"
    if os.path.exists(path):
        return

    # check=False: this might be built-in instead of being a module
    pmb.helpers.run.root(["modprobe", "binfmt_misc"], check=False)

    # check=False: we check it below and print a more helpful message on error
    pmb.helpers.run.root(
        ["mount", "-t", "binfmt_misc", "none", "/proc/sys/fs/binfmt_misc"], check=False
    )

    if not os.path.exists(path):
        link = "https://postmarketos.org/binfmt_misc"
        raise RuntimeError(f"Failed to set up binfmt_misc, see: {link}")


def migrate_success(work: Path, version: int) -> None:
    logging.info("Migration to version " + str(version) + " done")
    work.joinpath("version").write_text(str(version) + "\n")


def migrate_work_folder() -> None:
    # Read current version
    context = get_context()
    current = 0
    suffix: str | None = None
    current_with_suffix = ""
    path = context.config.work / "version"
    if os.path.exists(path):
        # pmb 2.3.x added a suffix due to conflicting work versions
        # We need to be able to handle that going forward
        current_with_suffix = path.read_text().rstrip()
        version_parts = current_with_suffix.split("-")
        current = int(version_parts[0])
        if len(version_parts) == 2:
            suffix = version_parts[1]

    # Compare version, print warning or do nothing
    required = pmb.config.work_version
    if current == required:
        return
    logging.info(
        "WARNING: Your work folder version needs to be migrated"
        f" (from version {current_with_suffix} to {required})!"
    )

    # version 6 and version 7 from 2.3.x branch are equivalent for this and we need to migrate
    if current == 6 or (current == 7 and suffix == "2.x"):
        # Ask for confirmation
        logging.info("Changelog:")
        logging.info("* Major refactor for pmb 3.0.0")
        logging.info("Migration will do the following:")
        logging.info("* Zap your chroots")
        if not pmb.helpers.cli.confirm():
            raise RuntimeError("Aborted.")

        # Zap chroots
        pmb.chroot.zap(False)

        # Update version file
        if suffix == "2.x":
            # If we come from 7-2.x, then we already updated the git urls and
            # can skip the 7->8 migration step
            migrate_success(context.config.work, 8)
            current = 8
        else:
            migrate_success(context.config.work, 7)
            current = 7

    if current == 7:
        # Ask for confirmation
        logging.info("Changelog:")
        logging.info("* Moved from gitlab.com to gitlab.postmarketOS.org")
        logging.info("Migration will do the following:")
        logging.info("* Update your pmaports remote URL")
        if not pmb.helpers.cli.confirm():
            raise RuntimeError("Aborted.")

        pmb.helpers.git.migrate_upstream_remote()
        try:
            pmb.helpers.git.get_upstream_remote(pkgrepo_default_path())
        except RuntimeError as exception:
            logging.error(
                "Couldn't find new upstream remote, migration failed."
                " Please try updating the remote manually with:\n"
                f" $ git -C '{pkgrepo_default_path()}' remote set-url origin 'https://gitlab.postmarketos.org/postmarketOS/pmaports.git'"
            )
            raise RuntimeError("Migration failed.") from exception

        # Update version file
        migrate_success(context.config.work, 8)
        current = 8

    # Can't migrate, user must delete it
    if current != required:
        raise NonBugError(
            "Sorry, we can't migrate that automatically. Please"
            " run 'pmbootstrap shutdown', then delete your"
            " current work folder manually ('sudo rm -rf "
            f"{context.config.work}') and start over with 'pmbootstrap"
            " init'. All your binary packages and caches will"
            " be lost."
        )


def normalize_hostname(hostname: str) -> str:
    """
    Fixup default hostnames so that they don't fail validate_hostname()

    This should not be called on user-chosen hostnames as those should fail
    """
    # Truncate length
    if len(hostname) > 63:
        hostname = hostname[:63]

    # Replace underscores with dashes
    if "_" in hostname:
        hostname = hostname.replace("_", "-")

    # We shouldn't have to fix the rest of the regex because the APKBUILDs'
    # device names shouldn't have any more invalid characters

    return hostname


def validate_hostname(hostname: str) -> bool:
    """
    Check whether the string is a valid hostname.

    Check is performed according to
    <http://en.wikipedia.org/wiki/Hostname#Restrictions_on_valid_host_names>
    """
    # Check length
    if len(hostname) > 63:
        logging.fatal(f"ERROR: Hostname '{hostname}' is too long.")
        return False

    if len(hostname) == 0:
        logging.fatal("ERROR: Hostnames must be at least one character.")
        return False

    # Check that it only contains valid chars
    if not re.match(r"^[0-9a-z-\.]*$", hostname):
        logging.fatal(
            "ERROR: Hostname must only contain letters (a-z), digits (0-9), minus signs "
            "(-), or periods (.)"
        )
        return False

    # Check that doesn't begin or end with a minus sign or period
    if re.search(r"^-|^\.|-$|\.$", hostname):
        logging.fatal("ERROR: Hostname must not begin or end with a minus sign or period")
        return False

    return True


"""
pmbootstrap uses this dictionary to save the result of expensive
results, so they work a lot faster the next time they are needed in the
same session. Usually the cache is written to and read from in the same
Python file, with code similar to the following:

def lookup(key):
    if key in pmb.helpers.other.cache["mycache"]:
        return pmb.helpers.other.cache["mycache"][key]
    ret = expensive_operation(args, key)
    pmb.helpers.other.cache["mycache"][key] = ret
    return ret
"""
cache: dict[str, Any] = {
    "apkindex": {},
}
