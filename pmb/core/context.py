# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

"""Global runtime context"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal, overload

from .config import Config


class TimeoutReason(Enum):
    CI_DETECTED = "running in CI based on autodetection (environment variable 'CI' set)"
    TIMEOUT_ARG = "timeout was explicitly set via the --timeout or -t argument"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class CommandTimeout:
    length: float
    reason: TimeoutReason


class Context:
    details_to_stdout: bool = False
    quiet: bool = False
    command_timeout: CommandTimeout | None = None
    sudo_timer: bool = False
    force: bool = False
    log: Path

    # assume yes to prompts
    assume_yes: bool = False

    # Operate offline
    offline: bool = False

    # The pmbootstrap subcommand
    command: str = ""

    ## FIXME: build options, should not be here ##
    # disable cross compilation and use QEMU
    cross: bool = False
    no_depends: bool = False
    ignore_depends: bool = False
    ccache: bool = True
    go_mod_cache: bool = False

    config: Config

    def __init__(self, config: Config) -> None:
        self.log = config.work / "log.txt"
        self.config = config


__context: Context


@overload
def get_context(allow_failure: Literal[False] = ...) -> Context: ...


@overload
def get_context(allow_failure: Literal[True] = ...) -> Context | None: ...


def get_context(allow_failure: bool = False) -> Context | None:
    """Get immutable global runtime context."""
    # We must defer this to first call to avoid
    # circular imports.
    if "__context" not in globals():
        if allow_failure:
            return None
        raise RuntimeError("Context not loaded yet")
    return __context


def set_context(context: Context) -> None:
    """Set global runtime context."""
    global __context

    if "__context" in globals():
        raise RuntimeError("Context already loaded")

    __context = context
