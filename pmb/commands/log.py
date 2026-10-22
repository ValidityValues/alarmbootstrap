# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import pmb.config
from pmb.core.context import get_context
from pmb.helpers import run
from pmb.types import PathString, RunOutputTypeDefault


def log(clear_log: bool, lines: int) -> None:
    context = get_context()
    log_testsuite = pmb.config.pmb_src / ".pytest_tmp/log_testsuite.txt"

    if clear_log:
        run.user(["truncate", "-s", "0", context.log])
        if log_testsuite.exists():
            run.user(["truncate", "-s", "0", log_testsuite])

    cmd: list[PathString] = ["tail", "-n", str(lines), "-F"]

    # Follow the testsuite's log file too if it exists. It will be created when
    # starting a test case that writes to it (git -C test grep log_testsuite).
    if log_testsuite.exists():
        cmd += [log_testsuite]

    # tail writes the last lines of the files to the terminal. Put the regular
    # log at the end, so that output is visible at the bottom (where the user
    # looks for an error / what's currently going on).
    cmd += [context.log]

    run.user(cmd, output=RunOutputTypeDefault.TUI)
