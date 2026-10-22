# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import collections
import glob
import os
import sys
from pathlib import Path
from typing import TypedDict

import pmb.chroot
import pmb.helpers.cli
from pmb.core import Chroot
from pmb.helpers import logging
from pmb.types import Env, RunOutputTypeDefault


class CiScriptDescriptor(TypedDict):
    description: str
    options: list[str]
    artifacts: str | None


def get_ci_scripts(topdir: Path) -> dict[str, CiScriptDescriptor]:
    """
    Find 'pmbootstrap ci'-compatible scripts inside a git repository, and
    parse their metadata (description, options). The reference is at:
    https://nura.eco/pmb-ci

    :param topdir: top directory of the git repository, get it with: pmb.helpers.git.get_topdir()

    :returns: a dict of CI scripts found in the git repository, e.g.
      {"ruff": {"description": "lint all python scripts", "options": []}, ...}
    """
    ret: dict[str, CiScriptDescriptor] = {}
    for script in glob.glob(f"{topdir}/.ci/*.sh"):
        is_pmb_ci_script = False
        description = ""
        options = []
        artifacts = None

        with open(script) as handle:
            for line in handle:
                if line.startswith(
                    ("# https://nura.eco/pmb-ci", "# https://postmarketos.org/pmb-ci")
                ):
                    is_pmb_ci_script = True
                elif line.startswith("# Description: "):
                    description = line.split(": ", 1)[1].rstrip()
                elif line.startswith("# Options: "):
                    options = line.split(": ", 1)[1].rstrip().split(" ")
                elif line.startswith("# Artifacts: "):
                    artifacts = line.split(": ", 1)[1].strip()
                elif not line.startswith("#"):
                    # Stop parsing after the block of comments on top
                    break

        if not is_pmb_ci_script:
            continue

        if not description:
            logging.error(f"ERROR: {script}: missing '# Description: …' line")
            sys.exit(1)

        for option in options:
            if option not in pmb.config.ci_valid_options:
                raise RuntimeError(
                    f"{script}: unsupported option '{option}'."
                    " Typo in script or pmbootstrap too old?"
                )

        short_name = os.path.basename(script).split(".", -1)[0]
        ret[short_name] = {"description": description, "options": options, "artifacts": artifacts}
    return ret


def sort_scripts_by_speed(scripts: dict[str, CiScriptDescriptor]) -> dict[str, CiScriptDescriptor]:
    """
    Order the scripts, so fast scripts run before slow scripts. Whether a
    script is fast or not is determined by the '# Options: slow' comment in
    the file.

    :param scripts: return of get_ci_scripts()

    :returns: same format as get_ci_scripts(), but as ordered dict with
      fast scripts before slow scripts

    """
    ret = collections.OrderedDict()

    # Fast scripts first
    for script_name, script in scripts.items():
        if "slow" in script["options"]:
            continue
        ret[script_name] = script

    # Then slow scripts
    for script_name, script in scripts.items():
        if "slow" not in script["options"]:
            continue
        ret[script_name] = script
    return ret


def ask_which_scripts_to_run(
    scripts_available: dict[str, CiScriptDescriptor],
) -> dict[str, CiScriptDescriptor]:
    """
    Display an interactive prompt about which of the scripts the user
    wishes to run, or all of them.

    :param scripts_available: same format as get_ci_scripts()

    :returns: either full scripts_available (all selected), or a subset

    """
    count = len(scripts_available.items())
    choices = []

    logging.info(f"Available CI scripts ({count}):")
    for script_name, script in scripts_available.items():
        extra = ""
        if "slow" in script["options"]:
            extra += " (slow)"
        logging.info(f"* {script_name}: {script['description']}{extra}")
        choices += [script_name]

    choice_regex = "|".join(choices)
    ci_regex = f"(all)|({choice_regex})(,({choice_regex}))*"
    choices += ["all"]
    logging.info('Fill a comma-separated list of scripts or "all"')
    selection = pmb.helpers.cli.ask(
        "Scripts", None, "all", validation_regex=ci_regex, complete=choices
    )
    if selection == "all":
        return scripts_available
    else:
        return {script: scripts_available[script] for script in selection.split(",")}


def copy_git_repo_to_chroot(topdir: Path, include_dot_git_dir: bool = False) -> None:
    """
    Create a tarball of the git repo (including unstaged changes and new
    files) and extract it in chroot_native.

    :param topdir: top directory of the git repository, get it with:
      pmb.helpers.git.get_topdir()
    :param include_dot_git_dir: Also include .git
    """
    chroot = Chroot.native()
    pmb.chroot.init(chroot)
    tarball_path = chroot / "tmp/git.tar.gz"
    files = pmb.helpers.git.get_files(topdir, include_dot_git_dir=include_dot_git_dir)

    with open(f"{tarball_path}.files", "w") as handle:
        for file in files:
            handle.write(file)
            handle.write("\n")

    pmb.helpers.run.user(["tar", "-cf", tarball_path, "-T", f"{tarball_path}.files"], topdir)

    ci_dir = Path("/home/pmos/ci")
    pmb.chroot.user(["rm", "-rf", ci_dir])
    pmb.chroot.user(["mkdir", ci_dir])
    pmb.chroot.user(["tar", "-xf", "/tmp/git.tar.gz"], working_dir=ci_dir)


def run_scripts(topdir: Path, scripts: dict[str, CiScriptDescriptor]) -> None:
    """
    Run one of the given scripts after another, either natively or in a
    chroot. Display a progress message and stop on error (without printing
    a python stack trace).

    :param topdir: top directory of the git repository, get it with:
      pmb.helpers.git.get_topdir()

    :param scripts: return of get_ci_scripts()

    """
    steps = len(scripts)
    step = 0
    repo_copied = False

    for script_name, script in scripts.items():
        step += 1

        where = "pmbootstrap chroot"
        if "native" in script["options"]:
            where = "native"

        script_path = f".ci/{script_name}.sh"
        logging.info(f"*** ({step}/{steps}) RUNNING CI SCRIPT: {script_path} [{where}] ***")

        if "native" in script["options"]:
            rc = pmb.helpers.run.user([script_path], topdir, output=RunOutputTypeDefault.TUI)
            continue
        else:
            # Run inside pmbootstrap chroot
            if not repo_copied:
                copy_git_repo_to_chroot(
                    topdir, include_dot_git_dir="with-dot-git" in script["options"]
                )
                repo_copied = True

            env: Env = {"TESTUSER": "pmos"}
            rc = pmb.chroot.root(
                [script_path],
                check=False,
                env=env,
                working_dir=Path("/home/pmos/ci"),
                output=RunOutputTypeDefault.TUI,
            )
        if rc:
            logging.error(f"ERROR: CI script failed: {script_name}")
            sys.exit(1)

        if script["artifacts"]:
            logging.info(f"Copy CI artifacts to ./ci-artifacts/{script_name}")
            path = Chroot.native().path / "home/pmos/ci" / script["artifacts"]
            target = topdir / "ci-artifacts" / script_name
            pmb.helpers.run.user(["rm", "-rf", target])
            pmb.helpers.run.user(["mkdir", "-p", target])
            pmb.helpers.run.user(["cp", "-r", path, target])
