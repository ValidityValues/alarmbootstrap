# Copyright 2026 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys
from pathlib import Path

import pmb.ci
import pmb.helpers.git
from pmb.helpers import logging


def ci(scripts: str, all: bool, fast: bool) -> None:
    topdir = pmb.helpers.git.get_topdir(Path.cwd())
    if not os.path.exists(topdir):
        logging.error(
            "ERROR: change your current directory to a git"
            " repository (e.g. pmbootstrap, pmaports) before running"
            " 'pmbootstrap ci'."
        )
        sys.exit(1)

    scripts_available = pmb.ci.get_ci_scripts(topdir)
    scripts_available = pmb.ci.sort_scripts_by_speed(scripts_available)
    if not scripts_available:
        logging.error(
            "ERROR: no supported CI scripts found in current git"
            " repository, see https://nura.eco/pmb-ci"
        )
        sys.exit(1)

    scripts_selected = {}
    if scripts:
        if all:
            raise RuntimeError("Combining --all with script names doesn't make sense")
        for script in scripts:
            if script not in scripts_available:
                logging.error(
                    f"ERROR: script '{script}' not found in git"
                    " repository, found these:"
                    f" {', '.join(scripts_available.keys())}"
                )
                sys.exit(1)
            scripts_selected[script] = scripts_available[script]
    elif all:
        scripts_selected = scripts_available

    if fast:
        for script, script_data in scripts_available.items():
            if "slow" not in script_data["options"]:
                scripts_selected[script] = script_data

    if not pmb.helpers.git.clean_worktree(topdir):
        logging.warning("WARNING: this git repository has uncommitted changes")

    if not scripts_selected:
        scripts_selected = pmb.ci.ask_which_scripts_to_run(scripts_available)

    pmb.ci.run_scripts(topdir, scripts_selected)
