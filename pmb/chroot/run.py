# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path, PurePath
from typing import Literal, overload

import pmb.chroot
import pmb.config
import pmb.helpers.run_core
from pmb.core import Chroot
from pmb.types import (
    Env,
    PathString,
    RunOutputType,
    RunOutputTypeDefault,
    RunOutputTypePopen,
    RunReturnType,
)


def rootm(
    cmds: Sequence[Sequence[PathString]],
    chroot: Chroot = Chroot.native(),
    working_dir: PurePath = PurePath("/"),
    output: RunOutputType = RunOutputTypeDefault.LOG,
    output_return: bool = False,
    check: bool | None = None,
    env: Env = {},
    disable_timeout: bool = False,
    add_proxy_env_vars: bool = True,
) -> RunReturnType:
    """
    Run a list of commands inside a chroot as root.

    :param env: dict of environment variables to be passed to the command, e.g.
                {"JOBS": "5"}
    :param working_dir: chroot-relative working directory
    :param add_proxy_env_vars: if True, preserve HTTP_PROXY etc. vars from host
                               environment. pmb.chroot.user sets this to False
                               when calling pmb.chroot.root, because it already
                               makes the variables part of the cmd argument.

    See pmb.helpers.run_core.core() for a detailed description of all other
    arguments and the return value.
    """
    # Convert any Path objects to their string representation
    cmd_strs = [[os.fspath(x) for x in cmd] for cmd in cmds]

    # Readable log message (without all the escaping)
    msg = f"({chroot}) % "
    for key, value in env.items():
        msg += f"{key}={value} "
    if working_dir != PurePath("/"):
        msg += f"cd {working_dir}; "
    msg += "; ".join([" ".join(cmd_str) for cmd_str in cmd_strs])

    # Merge env with defaults into env_all
    env_all: Env = {
        "CHARSET": "UTF-8",
        "HISTFILE": "~/.ash_history",
        "HOME": "/root",
        "LANG": "UTF-8",
        "PATH": pmb.config.chroot_path,
        "PYTHONUNBUFFERED": "1",
        "SHELL": "/bin/ash",
        "TERM": "xterm",
    }
    for key, value in env.items():
        env_all[key] = value
    if add_proxy_env_vars:
        pmb.helpers.run_core.add_proxy_env_vars(env_all)

    # Build the command in steps and run it, e.g.:
    # cmd: ["echo", "test"]
    # cmd_chroot: ["/sbin/chroot", "/..._native", "/bin/sh", "-c", "echo test"]
    # cmd_sudo: ["sudo", "env", "-i", "sh", "-c", "PATH=... /sbin/chroot ..."]
    executables = pmb.config.required_programs
    cmd_chroot: list[PathString] = [
        executables["chroot"],
        chroot.path,
        "/bin/sh",
        "-c",
        pmb.helpers.run_core.flat_cmd(cmd_strs, Path(working_dir)),
    ]
    cmd_sudo = pmb.config.sudo(
        [
            "env",
            "-i",
            executables["sh"],
            "-c",
            pmb.helpers.run_core.flat_cmd([cmd_chroot], env=env_all),
        ]
    )
    return pmb.helpers.run_core.core(
        msg, cmd_sudo, None, output, output_return, check, True, disable_timeout
    )


@overload
def root(
    cmds: Sequence[PathString],
    chroot: Chroot = ...,
    *,
    check: bool = ...,
) -> int: ...


@overload
def root(
    cmds: Sequence[PathString],
    chroot: Chroot = ...,
    working_dir: PurePath = ...,
    output: RunOutputTypePopen = ...,
    output_return: Literal[False] = ...,
    check: bool | None = ...,
    env: Env = ...,
    disable_timeout: bool = ...,
    add_proxy_env_vars: bool = ...,
) -> subprocess.Popen[bytes]: ...


@overload
def root(
    cmds: Sequence[PathString],
    chroot: Chroot = ...,
    working_dir: PurePath = ...,
    output: RunOutputTypeDefault = ...,
    output_return: Literal[False] = ...,
    check: bool | None = ...,
    env: Env = ...,
    disable_timeout: bool = ...,
    add_proxy_env_vars: bool = ...,
) -> int: ...


@overload
def root(
    cmds: Sequence[PathString],
    chroot: Chroot = ...,
    working_dir: PurePath = ...,
    output: RunOutputType = ...,
    output_return: Literal[True] = ...,
    check: bool | None = ...,
    env: Env = ...,
    disable_timeout: bool = ...,
    add_proxy_env_vars: bool = ...,
) -> str: ...


@overload
def root(
    cmds: Sequence[PathString],
    chroot: Chroot = ...,
    working_dir: PurePath = ...,
    output: RunOutputType = ...,
    output_return: bool = ...,
    check: bool | None = ...,
    env: Env = ...,
    disable_timeout: bool = ...,
    add_proxy_env_vars: bool = ...,
) -> subprocess.Popen[bytes] | int | str: ...


def root(
    cmds: Sequence[PathString],
    chroot: Chroot = Chroot.native(),
    working_dir: PurePath = PurePath("/"),
    output: RunOutputType = RunOutputTypeDefault.LOG,
    output_return: bool = False,
    check: bool | None = None,
    env: Env = {},
    disable_timeout: bool = False,
    add_proxy_env_vars: bool = True,
) -> RunReturnType:
    return rootm(
        [cmds],
        chroot,
        working_dir,
        output,
        output_return,
        check,
        env,
        disable_timeout,
        add_proxy_env_vars,
    )


def userm(
    cmds: Sequence[Sequence[PathString]],
    chroot: Chroot = Chroot.native(),
    working_dir: Path = Path("/"),
    output: RunOutputType = RunOutputTypeDefault.LOG,
    output_return: bool = False,
    check: bool | None = None,
    env: Env = {},
) -> RunReturnType:
    """
    Run a command inside a chroot as "user". We always use the BusyBox
    implementation of 'su', because other implementations may override the PATH
    environment variable (#1071).

    :param env: dict of environment variables to be passed to the command, e.g.
                {"JOBS": "5"}

    See pmb.helpers.run_core.core() for a detailed description of all other
    arguments and the return value.
    """
    env = env.copy()
    pmb.helpers.run_core.add_proxy_env_vars(env)

    if "HOME" not in env:
        env["HOME"] = "/home/pmos"

    flat_cmd = pmb.helpers.run_core.flat_cmd(cmds, env=env)
    cmd = ["busybox", "su", "pmos", "-c", flat_cmd]
    return pmb.chroot.root(
        cmd, chroot, working_dir, output, output_return, check, {}, add_proxy_env_vars=False
    )


@overload
def user(
    cmd: Sequence[PathString],
    chroot: Chroot = ...,
    working_dir: Path = ...,
    output: RunOutputTypePopen = ...,
    output_return: Literal[False] = ...,
    check: bool | None = ...,
    env: Env = ...,
) -> subprocess.Popen[bytes]: ...


@overload
def user(
    cmd: Sequence[PathString],
    chroot: Chroot = ...,
    working_dir: Path = ...,
    output: RunOutputTypeDefault = ...,
    output_return: Literal[False] = ...,
    check: bool | None = ...,
    env: Env = ...,
) -> int: ...


@overload
def user(
    cmd: Sequence[PathString],
    chroot: Chroot = ...,
    working_dir: Path = ...,
    output: RunOutputType = ...,
    output_return: Literal[True] = ...,
    check: bool | None = ...,
    env: Env = ...,
) -> str: ...


def user(
    cmd: Sequence[PathString],
    chroot: Chroot = Chroot.native(),
    working_dir: Path = Path("/"),
    output: RunOutputType = RunOutputTypeDefault.LOG,
    output_return: bool = False,
    check: bool | None = None,
    env: Env = {},
) -> RunReturnType:
    return userm([cmd], chroot, working_dir, output, output_return, check, env)


def user_exists(username: str, chroot: Chroot = Chroot.native()) -> bool:
    """
    Checks if username exists in the system

    :param username: User name
    :returns: bool
    """
    output = pmb.chroot.root(
        ["getent", "passwd", username], chroot, output_return=True, check=False
    )
    return len(output) > 0
