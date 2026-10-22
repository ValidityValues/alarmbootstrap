# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import configparser
import os
import sys
from pathlib import Path
from typing import Final

import pmb.config
import pmb.helpers.git
import pmb.parse.version
from pmb.core.context import get_context
from pmb.core.pkgrepo import (
    pkgrepo_default_path,
    pkgrepo_name,
    pkgrepo_paths,
    pkgrepo_relative_path,
)
from pmb.helpers import logging
from pmb.helpers.exceptions import NonBugError
from pmb.meta import Cache
from pmb.types import RunOutputTypeDefault


def clone(do_shallow: bool = False) -> None:
    logging.info("Setting up the native chroot and cloning the package build recipes (pmaports)...")

    # Set up the native chroot and clone pmaports
    pmb.helpers.git.clone("pmaports", do_shallow)


def check_version_pmaports(real: str) -> None:
    # Compare versions
    min = pmb.config.pmaports_min_version
    if pmb.parse.version.compare(real, min) >= 0:
        return

    # Outated error
    logging.info(
        "NOTE: your pmaports folder has version "
        + real
        + ", but"
        + " version "
        + min
        + " is required."
    )
    raise RuntimeError("Run 'pmbootstrap pull' to update your pmaports.")


def check_version_pmbootstrap(min_ver: str) -> None:
    # Compare versions
    real = pmb.__version__
    if pmb.parse.version.compare(real, min_ver) >= 0:
        return

    # Show versions
    logging.info(
        f"NOTE: you are using pmbootstrap version {real}, but version {min_ver} is required."
    )

    # Error for git clone
    pmb_src = pmb.config.pmb_src
    if (pmb_src / ".git").exists():
        raise RuntimeError(
            "Please update your local pmbootstrap repository."
            f" Usually with: 'git -C \"{pmb_src}\" pull'"
        )

    # Error for package manager installation
    raise RuntimeError(
        "Please update your pmbootstrap version (with your"
        " distribution's package manager, or with pip, "
        " depending on how you have installed it). If that is"
        " not possible, consider cloning the latest version"
        " of pmbootstrap from git."
    )


@Cache()
def read_config_repos() -> dict[str, configparser.SectionProxy]:
    """Read the sections starting with "repo:" from pmaports.cfg."""
    cfg = configparser.ConfigParser()
    cfg.read(f"{pkgrepo_default_path()}/pmaports.cfg")

    ret = {}
    for section in cfg:
        if not section.startswith("repo:"):
            continue
        repo = section.split("repo:", 1)[1]
        ret[repo] = cfg[section]

    return ret


@Cache("aports", "add_systemd_prefix")
def read_config(
    aports: Path | None = None, add_systemd_prefix: bool = True
) -> configparser.SectionProxy:
    """
    Read and verify pmaports.cfg. If aports is not
    specified and systemd is enabled, the returned channel
    will be the systemd one (e.g. systemd-edge instead of edge)
    since we'll use the first pkgrepo which is systemd.
    """
    if aports is None:
        aports = pkgrepo_paths()[0]

    systemd = pkgrepo_name(aports) == "systemd"
    # extra-repos don't have a pmaports.cfg
    # so jump up the main aports dir
    if "extra-repos" in aports.parts:
        aports = pkgrepo_relative_path(aports)[0]

    # Migration message
    if not os.path.exists(aports):
        logging.error(f"ERROR: pmaports dir not found: {aports}")
        logging.error("Did you run 'pmbootstrap init'?")
        sys.exit(1)

    # Require the config
    path_cfg = aports / "pmaports.cfg"
    if not os.path.exists(path_cfg):
        raise RuntimeError(f"Invalid pmaports repository, could not find the config: {path_cfg}")

    # Load the config
    cfg = configparser.ConfigParser()
    cfg.read(path_cfg)
    ret = cfg["pmaports"]

    # Version checks
    check_version_pmaports(ret["version"])
    check_version_pmbootstrap(ret["pmbootstrap_min_version"])

    if systemd and add_systemd_prefix:
        ret["channel"] = "systemd-" + ret["channel"]

    return ret


def all_channels() -> list[str]:
    """Get a list of all channels for all pkgrepos."""
    ret = {read_config(repo)["channel"] for repo in pkgrepo_paths()}

    logging.verbose(f"all_channels: {ret}")
    return list(ret)


def read_config_channel() -> pmb.helpers.git.ChannelInfo:
    """
    Get the properties of the currently active channel in pmaports.git.

    As specified in channels.cfg (https://postmarketos.org/channels.cfg).

    :returns: {"description: ...,
               "branch_pmaports": ...,
               "branch_aports": ...,
               "mirrordir_alpine": ...}

    """
    aports = pkgrepo_default_path()
    channel = read_config(aports)["channel"]
    channels_cfg = pmb.helpers.git.parse_channels_cfg(aports)

    if channel in channels_cfg["channels"]:
        return channels_cfg["channels"][channel]

    # Channel not in channels.cfg, try to be helpful
    branch = pmb.helpers.git.rev_parse(aports, extra_args=["--abbrev-ref"])
    remote = pmb.helpers.git.get_upstream_remote(aports)
    logging.info(
        "NOTE: fix the error by rebasing or cherry picking relevant"
        " commits from this branch onto a branch that is on a"
        " supported channel: main, v24.06, …"
    )
    logging.info(
        "NOTE: as workaround, you may pass --config-channels with a"
        " custom channels.cfg. Reference:"
        " https://postmarketos.org/channels.cfg"
    )
    raise RuntimeError(
        f"Current branch '{branch}' of pmaports.git is on"
        f" channel '{channel}', but this channel was not"
        f" found in channels.cfg (of {remote}/main"
        " branch). Looks like a very old branch."
    )


def init(do_shallow_clone: bool = False) -> None:
    if not os.path.exists(pkgrepo_default_path()):
        clone(do_shallow_clone)
    read_config()


DEVELOPMENT_CHANNEL: Final[str] = "edge"


def switch_to_channel_branch(channel_new: str) -> bool:
    """
    Checkout the channel's branch in pmaports.git.

    :channel_new: channel name (e.g. "edge", "v21.03")

    :returns: True if another branch was checked out, False otherwise
    """
    aports = pkgrepo_default_path()
    config = get_context().config

    # list current and new branches/channels
    channels_cfg = pmb.helpers.git.parse_channels_cfg(aports)
    branch_new = channels_cfg["channels"][channel_new]["branch_pmaports"]
    branch_current = pmb.helpers.git.rev_parse(aports, extra_args=["--abbrev-ref"])

    # Check current pmaports branch channel
    channel_current = read_config(aports)["channel"]
    # If we are on edge and on master but edge calls for main
    if (
        channel_current == DEVELOPMENT_CHANNEL
        and branch_current == "master"
        and branch_new == "main"
    ):
        logging.info("NOTE: master was renamed to main, switching to it")
        branch_new = "main"
    elif channel_current == channel_new:
        return False

    if (
        branch_current == "master_staging_systemd"
        and channel_new == DEVELOPMENT_CHANNEL
        and pmb.config.is_systemd_selected(config)
    ):
        logging.info("NOTE: master_staging_systemd was merged into main, switching to it")

    logging.info(
        f"Currently checked out branch '{branch_current}' of"
        f" pmaports.git is on channel '{channel_current}'."
    )
    logging.info(f"Switching to branch '{branch_new}' on channel '{channel_new}'...")

    # Make sure we don't have mounts related to the old channel
    pmb.chroot.shutdown()

    # We need to make sure the branch exists in case --shallow-initial-clone previously was used.
    # Checking whether args.shallow_initial_clone is True would not solve this problem as a user
    # could use --shallow-initial-clone when cloning for the first time, then call init without the
    # flag subsequent times without the repository ever ending up "deep cloned". As such, check for
    # the presence of the branch instead of whether the flag is True.
    if pmb.helpers.run.user(
        ["git", "show-ref", "--quiet", "--branches", branch_new], aports, check=False
    ):
        logging.info(f"Branch {branch_new} doesn't exist, attempting to fetch it")

        if pmb.helpers.run.user(
            ["git", "fetch", "--depth=1", "origin", f"{branch_new}:{branch_new}"],
            aports,
            RunOutputTypeDefault.INTERACTIVE,
            check=False,
        ):
            raise NonBugError(f"Failed to fetch {branch_new}!")

    # Attempt to switch branch (git gives a nice error message, mentioning
    # which files need to be committed/stashed, so just pass it through)
    if pmb.helpers.run.user(
        ["git", "switch", branch_new], aports, RunOutputTypeDefault.INTERACTIVE, check=False
    ):
        raise NonBugError(
            "Failed to switch branch. Go to your pmaports and"
            " fix what git complained about, then try again: "
            f"{aports}"
        )

    # Verify pmaports.cfg on new branch
    read_config()
    return True


def install_githooks() -> None:
    aports = pkgrepo_default_path()
    hooks_dir = aports / ".githooks"
    if not hooks_dir.exists():
        logging.info("No .githooks dir found")
        return
    for h in os.listdir(hooks_dir):
        src = os.path.join(hooks_dir, h)
        # Use git default hooks dir so users can ignore our hooks
        # if they dislike them by setting "core.hooksPath" git config
        dst = aports / ".git/hooks" / h
        if pmb.helpers.run.user(["cp", src, dst], check=False):
            logging.warning(f"WARNING: Copying git hook failed: {dst}")
