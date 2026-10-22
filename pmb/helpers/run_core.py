# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import fcntl
import os
import selectors
import shlex
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, overload

import pmb.helpers.run
from pmb.config.sudo import which_sudo
from pmb.core.context import get_context
from pmb.helpers import logging
from pmb.helpers.exceptions import CommandFailedError, NonBugError
from pmb.types import (
    Env,
    PathString,
    RunOutputType,
    RunOutputTypeDefault,
    RunOutputTypePopen,
    RunReturnType,
)

"""For a detailed description of all output modes, read the description of
   core() at the bottom. All other functions in this file get (indirectly)
   called by core(). """


def flat_cmd(
    cmds: Sequence[Sequence[PathString]], working_dir: Path | None = None, env: Env = {}
) -> str:
    """
    Convert a shell command passed as list into a flat shell string with proper escaping.

    :param cmds: list of commands as list, e.g. ["echo", "string with spaces"]
    :param working_dir: when set, prepend "cd ...;" to execute the command
                        in the given working directory
    :param env: dict of environment variables to be passed to the command, e.g.
                {"JOBS": "5"}
    :returns: the flat string, e.g.
              echo 'string with spaces'
              cd /home/pmos;echo 'string with spaces'
    """
    # Merge env and cmd into escaped list
    escaped = [f"{key}={shlex.quote(os.fspath(value))}" for key, value in env.items()]
    for cmd in cmds:
        escaped.extend(shlex.quote(os.fspath(cmd[i])) for i in range(len(cmd)))
        escaped.append(";")

    # Prepend working dir
    ret = " ".join(escaped)
    if working_dir is not None:
        ret = "cd " + shlex.quote(str(working_dir)) + ";" + ret

    return ret


def sanity_checks(
    output: RunOutputType = RunOutputTypeDefault.LOG,
    output_return: bool = False,
    check: bool | None = None,
) -> None:
    """
    Raise an exception if the parameters passed to core() don't make sense.

    (all parameters are described in core() below).
    """
    # Prevent setting the check parameter with output="background".
    # The exit code won't be checked when running in background, so it would
    # always by check=False. But we prevent it from getting set to check=False
    # as well, so it does not look like you could change it to check=True.
    if check is not None and output == RunOutputTypePopen.BACKGROUND:
        raise RuntimeError("Can't use check with output: background")

    if output_return and output in [RunOutputTypeDefault.TUI, RunOutputTypePopen.BACKGROUND]:
        raise RuntimeError(f"Can't use output_return with output: {output}")


def background(
    cmd: PathString | Sequence[PathString], working_dir: PathString | None = None
) -> subprocess.Popen[bytes]:
    """Run a subprocess in background and redirect its output to the log."""
    ret = subprocess.Popen(
        cmd, stdout=pmb.helpers.logging.logfd, stderr=pmb.helpers.logging.logfd, cwd=working_dir
    )
    logging.debug(f"New background process: pid={ret.pid}, output=background")
    return ret


def pipe(
    cmd: PathString | Sequence[PathString], working_dir: PathString | None = None
) -> subprocess.Popen[bytes]:
    """Run a subprocess in background and redirect its output to a pipe."""
    ret = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        stderr=pmb.helpers.logging.logfd,
        cwd=working_dir,
    )
    logging.verbose(f"New background process: pid={ret.pid}, output=pipe")
    return ret


@overload
def pipe_read(
    process: subprocess.Popen[bytes],
    output_to_stdout: bool = ...,
    output_log: bool = ...,
    output_return: Literal[False] = ...,
    output_return_buffer: None = ...,
) -> None: ...


@overload
def pipe_read(
    process: subprocess.Popen[bytes],
    output_to_stdout: bool = ...,
    output_log: bool = ...,
    output_return: Literal[True] = ...,
    output_return_buffer: list[bytes] = ...,
) -> None: ...


@overload
def pipe_read(
    process: subprocess.Popen[bytes],
    output_to_stdout: bool = ...,
    output_log: bool = ...,
    output_return: bool = ...,
    output_return_buffer: list[bytes] | None = ...,
) -> None: ...


def pipe_read(
    process: subprocess.Popen[bytes],
    output_to_stdout: bool = False,
    output_log: bool = True,
    output_return: bool = False,
    output_return_buffer: list[bytes] | None = None,
) -> None:
    """
    Read all output from a subprocess, copy it to the log and optionally stdout and a buffer variable.

    This is only meant to be called by foreground_pipe() below.

    :param process: subprocess.Popen instance
    :param output_to_stdout: copy all output to pmbootstrap's stdout
    :param output_return: when set to True, output_return_buffer will be
                          extended
    :param output_return_buffer: list of bytes that gets extended with the
                                 current output in case output_return is True.
    """
    while True:
        # Copy available output
        process_stdout = process.stdout
        if process_stdout is None:
            raise RuntimeError("subprocess has no stdout?")
        out = process_stdout.readline()
        if len(out):
            if output_log:
                pmb.helpers.logging.logfd.buffer.write(out)
            if output_to_stdout:
                sys.stdout.buffer.write(out)
            if output_return:
                if output_return_buffer is None:
                    raise AssertionError
                output_return_buffer.append(out)
            continue

        # No more output (flush buffers)
        pmb.helpers.logging.logfd.flush()
        if output_to_stdout:
            sys.stdout.flush()
        return


# FIXME: The docstring claims that ppids should be a list of "process ID tuples", but in practice it
# gets called with a list of string lists for the ppids argument.
def kill_process_tree(pid: int | str, ppids: list[list[str]], sudo: bool) -> None:
    """
    Recursively kill a pid and its child processes.

    :param pid: process id that will be killed
    :param ppids: list of process id and parent process id tuples (pid, ppid)
    :param sudo: use sudo to kill the process
    """
    if sudo:
        pmb.helpers.run.root(["kill", "-9", str(pid)], check=False)
    else:
        pmb.helpers.run.user(["kill", "-9", str(pid)], check=False)

    for child_pid, child_ppid in ppids:
        if child_ppid == str(pid):
            kill_process_tree(child_pid, ppids, sudo)


def kill_command(pid: int, sudo: bool) -> None:
    """
    Kill a command process and recursively kill its child processes.

    :param pid: process id that will be killed
    :param sudo: use sudo to kill the process
    """
    cmd = ["ps", "-e", "-o", "pid,ppid"]
    ret = subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
    ppids = []
    proc_entries = ret.stdout.decode("utf-8").rstrip().split("\n")[1:]
    for row in proc_entries:
        items = row.split()
        if len(items) != 2:
            raise RuntimeError("Unexpected ps output: " + row)
        ppids.append(items)

    kill_process_tree(pid, ppids, sudo)


def foreground_pipe(
    cmd: PathString | Sequence[PathString],
    working_dir: Path | None = None,
    output_to_stdout: bool = False,
    output_return: bool = False,
    output_log: bool = True,
    output_timeout: bool = True,
    sudo: bool = False,
    stdin: int | None = None,
) -> tuple[int, str]:
    """
    Run a subprocess in foreground with redirected output.

    Optionally kill it after being silent for too long.

    :param cmd: command as list, e.g. ["echo", "string with spaces"]
    :param working_dir: path in host system where the command should run
    :param output_to_stdout: copy all output to pmbootstrap's stdout
    :param output_return: return the output of the whole program
    :param output_timeout: kill the process when it doesn't print any output
                           after a certain time (configured with --timeout)
                           and raise a RuntimeError exception
    :param sudo: use sudo to kill the process when it hits the timeout
    :returns: (code, output)
              * code: return code of the program
              * output: ""
              * output: full program output string (output_return is True)
    """
    context = pmb.core.context.get_context()
    # Start process in background (stdout and stderr combined)
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=working_dir, stdin=stdin
    )

    # Make process.stdout non-blocking
    stdout = process.stdout or None
    if not stdout:
        raise RuntimeError("Process has no stdout?!")

    handle = stdout.fileno()
    flags = fcntl.fcntl(handle, fcntl.F_GETFL)
    fcntl.fcntl(handle, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    # While process exists wait for output (with timeout)
    output_buffer: list[bytes] = []
    with selectors.DefaultSelector() as sel:
        sel.register(stdout, selectors.EVENT_READ)
        while process.poll() is None:
            if context.command_timeout is not None:
                wait_start = time.perf_counter()
                timeout = context.command_timeout.length
                try:
                    sel.select(timeout)
                except OverflowError as exception:
                    raise NonBugError(
                        f"Specified timeout ({timeout}) isn't valid on this platform, maybe try something smaller ({exception})."
                    ) from exception

                # On timeout raise error (we need to measure time on our own, because
                # select() may exit early even if there is no data to read and the
                # timeout was not reached.)
                if output_timeout:
                    wait_end = time.perf_counter()
                    if wait_end - wait_start >= timeout:
                        logging.info(
                            f"Process did not write any output for {timeout} seconds. Killing it. Reason: {context.command_timeout.reason}"
                        )
                        logging.info("NOTE: The timeout can be increased with 'pmbootstrap -t'.")
                        kill_command(process.pid, sudo)
                        continue
            else:
                # Block until output is received when no timeout is configured
                sel.select(None)

            # Read all currently available output
            pipe_read(process, output_to_stdout, output_log, output_return, output_buffer)

        # There may still be output after the process quit
        pipe_read(process, output_to_stdout, output_log, output_return, output_buffer)

    # Return the return code and output (the output gets built as list of
    # output chunks and combined at the end, this is faster than extending the
    # combined string with each new chunk)
    return (process.returncode, b"".join(output_buffer).decode("utf-8"))


def foreground_tui(
    cmd: PathString | Sequence[PathString], working_dir: PathString | None = None
) -> int:
    """
    Run a subprocess in foreground without redirecting any of its output.

    This is the only way text-based user interfaces (ncurses programs like
    vim, nano or the kernel's menuconfig) work properly.
    """
    logging.debug("*** output passed to pmbootstrap stdout, not to this log ***")
    process = subprocess.Popen(cmd, cwd=working_dir)
    return process.wait()


def check_return_code(code: int, log_message: str) -> None:
    """
    Check the return code of a command.

    :param code: exit code to check
    :param log_message: simplified and more readable form of the command, e.g.
                        "(native) % echo test" instead of the full command with
                        entering the chroot and more escaping
    :raises RuntimeError: when the code indicates that the command failed
    """
    if code:
        logging.debug("^" * 70)
        log_file = get_context().log
        logging.info(
            f"NOTE: The failed command's output is above the ^^^ line in the log file: {log_file}"
        )
        raise CommandFailedError(f"Command failed (exit code {code}): " + log_message)


def sudo_timer_iterate() -> None:
    """Run sudo -v and schedule a new timer to repeat the same."""
    if which_sudo() == "sudo":
        subprocess.Popen(["sudo", "-v"]).wait()
    else:
        subprocess.Popen(pmb.config.sudo(["true"])).wait()

    timer = threading.Timer(interval=60, function=sudo_timer_iterate)
    timer.daemon = True
    timer.start()


def sudo_timer_start() -> None:
    """Start a timer to call sudo -v periodically, so that the password is only needed once."""
    if "sudo_timer_active" in pmb.helpers.other.cache:
        return
    pmb.helpers.other.cache["sudo_timer_active"] = True

    sudo_timer_iterate()


def add_proxy_env_vars(env: Env) -> None:
    """
    Add proxy environment variables from host to the environment of the command we are running.

    :param env: dict of environment variables, it will be extended with all of the proxy env vars
        that are set on the host
    """
    proxy_env_vars = [
        "FTP_PROXY",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "HTTP_PROXY_AUTH",
        "ftp_proxy",
        "http_proxy",
        "https_proxy",
    ]

    for var in proxy_env_vars:
        if var in os.environ:
            env[var] = os.environ[var]


def core(
    log_message: str,
    cmd: Sequence[PathString],
    working_dir: Path | None = None,
    output: RunOutputType = RunOutputTypeDefault.LOG,
    output_return: bool = False,
    check: bool | None = None,
    sudo: bool = False,
    disable_timeout: bool = False,
) -> RunReturnType:
    """
    Run a command and create a log entry.

    This is a low level function not meant to be used directly. Use one of the
    following instead: pmb.helpers.run.user(), pmb.helpers.run.root(),
    pmb.chroot.user(), pmb.chroot.root()

    :param log_message: simplified and more readable form of the command, e.g.
                        "(native) % echo test" instead of the full command with
                        entering the chroot and more escaping
    :param cmd: command as list, e.g. ["echo", "string with spaces"]
    :param working_dir: path in host system where the command should run
    :param output: where to write the output (stdout and stderr) of the
                   process. We almost always write to the log file, which can
                   be read with "pmbootstrap log" (output values: LOG,
                   STDOUT, INTERACTIVE, BACKGROUND), so it's easy to
                   trace what pmbootstrap does.

                   The exceptions are TUI (text-based user interface), where
                   it does not make sense to write to the log file (think of
                   ncurses UIs, such as "menuconfig") and "pipe" where the
                   output is written to a pipe for manual asynchronous
                   consumption by the caller.

                   When the output is not set to INTERACTIVE, TUI,
                   BACKGROUND or PIPE, we kill the process if it does not
                   output anything for 5 minutes (time can be set with
                   "pmbootstrap --timeout").

                   The table below shows all possible values along with
                   their properties. "wait" indicates that we wait for the
                   process to complete.

        ============  =======  ==========  =============  ====  ==========
        output value  timeout  out to log  out to stdout  wait  pass stdin
        ============  =======  ==========  =============  ====  ==========
        LOG           x        x                          x
        STDOUT        x        x           x              x
        INTERACTIVE            x           x              x     x
        TUI                                x              x     x
        BACKGROUND             x
        PIPE
        NULL
        ============  =======  ==========  =============  ====  ==========

    :param output_return: in addition to writing the program's output to the
        destinations above in real time, write to a buffer and return it as string when the
        command has completed. This is not possible when output is "background", "pipe" or "tui".
    :param check: an exception will be raised when the command's return code is not 0.
        Set this to False to disable the check. This parameter can not be used when the output is
        "background" or "pipe".
    :param sudo: use sudo to kill the process when it hits the timeout.
    :returns: * program's return code (default)
              * subprocess.Popen instance (output is "background" or "pipe")
              * the program's entire output (output_return is True)
    """
    sanity_checks(output, output_return, check)
    context = pmb.core.context.get_context()

    if context.sudo_timer and sudo:
        sudo_timer_start()

    # Log simplified and full command (pmbootstrap -v)
    logging.debug(log_message)
    logging.verbose("run: " + str(cmd))

    # try:
    #     input("Press Enter to continue...")
    # except KeyboardInterrupt as e:
    #     raise e

    # Background
    if output == RunOutputTypePopen.BACKGROUND:
        return background(cmd, working_dir)

    # Pipe
    if output == RunOutputTypePopen.PIPE:
        return pipe(cmd, working_dir)

    # Foreground
    output_after_run = ""
    if output == RunOutputTypeDefault.TUI:
        # Foreground TUI
        code = foreground_tui(cmd, working_dir)
    else:
        # Foreground pipe (always redirects to the error log file)
        output_to_stdout = False
        if not context.details_to_stdout and output.is_to_stdout():
            output_to_stdout = True

        output_timeout = output.has_timeout() and not disable_timeout

        stdin = None if output.has_pass_stdin() else subprocess.DEVNULL

        (code, output_after_run) = foreground_pipe(
            cmd,
            working_dir,
            output_to_stdout,
            output_return,
            output != RunOutputTypeDefault.NULL,
            output_timeout,
            sudo,
            stdin,
        )

    # Check the return code
    if check is not False:
        check_return_code(code, log_message)

    # Return (code or output string)
    return output_after_run if output_return else code
