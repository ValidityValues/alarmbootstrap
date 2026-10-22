# Copyright 2026 Oliver Smith, Hugo Posnic
# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from typing import NoReturn

import pmb.config
import pmb.config.other
import pmb.helpers.git
from pmb.core import Config
from pmb.core.context import get_context


def print_status_line(key: str, value: str) -> None:
    styles = pmb.config.styles
    key = f"{styles['GREEN']}{key}{styles['END']}:"
    padding = 17

    print(f"{key.ljust(padding)} {value}")


def print_channel() -> None:
    pmaports_cfg = pmb.config.pmaports.read_config()
    channel = pmaports_cfg["channel"]

    # Get branch name (if on branch) or current commit
    path = pmb.helpers.git.get_path("pmaports")
    ref = pmb.helpers.git.rev_parse(path, extra_args=["--abbrev-ref"], silent=True)
    if ref == "HEAD":
        ref = pmb.helpers.git.rev_parse(path, silent=True)[0:8]

    if not pmb.helpers.git.clean_worktree(path, silent=True):
        ref += ", dirty"

    value = f"{channel} (pmaports: {ref})"
    print_status_line("Channel", value)


def print_device(config: Config) -> None:
    kernel = ""
    if pmb.parse._apkbuild.kernels(config.device):
        kernel = f", kernel: {config.kernel}"

    value = f"{config.device} ({pmb.parse.deviceinfo().arch}{kernel})"
    print_status_line("Device", value)


def print_ui(config: Config) -> None:
    print_status_line("UI", config.ui)


def print_systemd(config: Config) -> None:
    yesno, reason = pmb.config.other.systemd_selected_str(config)
    print_status_line("systemd", f"{yesno} ({reason})")


def print_status() -> None:
    config = get_context().config
    print_channel()
    print_device(config)
    print_ui(config)
    print_systemd(config)


def status() -> NoReturn:
    print_status()
    # Do not print the DONE! line
    sys.exit(0)
