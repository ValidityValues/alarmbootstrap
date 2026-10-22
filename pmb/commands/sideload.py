# Copyright 2026 Stefan Hansson, Martijn Braam
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import shlex
from pathlib import Path

import pmb.build
import pmb.config.pmaports
import pmb.helpers.run
import pmb.helpers.run_core
import pmb.parse.apkindex
from pmb.core.arch import Arch
from pmb.core.context import get_context
from pmb.helpers import logging
from pmb.helpers.file import is_apk
from pmb.types import PathString, RunOutputTypeDefault

su_cmd = "_su=$(command -v sudo >/dev/null && echo sudo || (command -v doas >/dev/null && echo doas || echo run0)); $_su"
ssh_opts = [
    "-o",
    "ControlMaster=auto",
    "-o",
    "ControlPath='~/.ssh/controlmaster_%r@%h:%p'",
    "-o",
    "ControlPersist=60",
]


def scp_abuild_key(user: str, host: str, port: str) -> None:
    """
    Copy the building key of the local installation to the target device,
    so it trusts the apks that were signed here.

    :param user: target device ssh username
    :param host: target device ssh hostname
    :param port: target device ssh port
    """
    keys = list((get_context().config.work / "config_abuild").glob("*.pub"))
    key = keys[0]
    key_name = os.path.basename(key)

    logging.info(f"Copying signing key ({key_name}) to {user}@{host}")
    command: list[PathString] = ["scp", *ssh_opts, "-P", port, key, f"{user}@{host}:/tmp"]
    pmb.helpers.run.user(command, output=RunOutputTypeDefault.INTERACTIVE)

    logging.info(f"Installing signing key at {user}@{host}")
    keyname = os.path.join("/tmp", os.path.basename(key))
    remote_cmd_l: list[PathString] = [
        "mv",
        "-n",
        keyname,
        "/etc/apk/keys/",
    ]
    remote_cmd = pmb.helpers.run_core.flat_cmd([remote_cmd_l])
    full_cmd = shlex.quote(f"{su_cmd} {remote_cmd}")
    command = ["ssh", *ssh_opts, "-t", "-p", port, f"{user}@{host}", f"sh -c {full_cmd}"]
    pmb.helpers.run.user(command, output=RunOutputTypeDefault.TUI)


def ssh_find_arch(user: str, host: str, port: str) -> Arch:
    """Connect to a device via ssh and query the architecture."""
    logging.info(f"Querying architecture of {user}@{host}")
    # Run command in a subshell in case the foreign device has a weird uname
    # implementation, e.g. Nushell.
    architecture_cmd = shlex.quote("uname -m")
    command = ["ssh", *ssh_opts, "-p", port, f"{user}@{host}", f"sh -c {architecture_cmd}"]
    output = pmb.helpers.run.user_output(command)
    # Split by newlines so we can pick out any irrelevant output, e.g. the "permanently
    # added to list of known hosts" warnings.
    output_lines = output.strip().splitlines()
    # Pick out last line which should contain the foreign device's architecture
    foreign_machine_type = output_lines[-1]
    return Arch.from_machine_type(foreign_machine_type)


def ssh_install_apks(
    user: str,
    host: str,
    port: str,
    paths: list[Path],
    install_offline: bool,
    allow_untrusted: bool,
) -> None:
    """
    Copy binary packages via SCP and install them via SSH.

    :param user: target device ssh username
    :param host: target device ssh hostname
    :param port: target device ssh port
    :param paths: list of absolute paths to locally stored apks
    """
    remote_paths = [os.path.join("/tmp", os.path.basename(path)) for path in paths]

    logging.info(f"Copying packages to {user}@{host}")
    command: list[PathString] = ["scp", *ssh_opts, "-P", port, *paths, f"{user}@{host}:/tmp"]
    pmb.helpers.run.user(command, output=RunOutputTypeDefault.INTERACTIVE)

    logging.info(f"Installing packages at {user}@{host}")
    add_cmd_list = ["apk", "--wait", "30", "--timeout", "5"]
    if install_offline:
        add_cmd_list.append("--no-network")
    if allow_untrusted:
        add_cmd_list.append("--allow-untrusted")
    add_cmd_list.extend(["add", *remote_paths])
    add_cmd = pmb.helpers.run_core.flat_cmd([add_cmd_list])
    clean_cmd = pmb.helpers.run_core.flat_cmd([["rm", *remote_paths]])
    add_cmd_complete = shlex.quote(f"{su_cmd} {add_cmd} rc=$?; {clean_cmd} exit $rc")
    # Run apk command in a subshell in case the foreign device has a non-POSIX shell.
    command = ["ssh", *ssh_opts, "-t", "-p", port, f"{user}@{host}", f"sh -c {add_cmd_complete}"]
    pmb.helpers.run.user(command, output=RunOutputTypeDefault.TUI)


def sideload(
    user: str,
    host: str,
    port: str,
    arch: Arch | None,
    copy_key: bool,
    pkgnames: list[str],
    allow_untrusted: bool,
) -> None:
    """
    Build packages if necessary and install them via SSH.

    :param user: target device ssh username
    :param host: target device ssh hostname
    :param port: target device ssh port
    :param arch: target device architecture
    :param copy_key: copy the abuild key too
    :param pkgnames: list of pkgnames to be built
    :param allow_untrusted: whether to add --allow-untrusted to the apk add invocation
    """
    paths = []

    if arch is None:
        arch = ssh_find_arch(user, host, port)

    context = get_context()
    to_build = []
    install_offline = True
    for pkgname in pkgnames:
        data_repo = pmb.parse.apkindex.package(pkgname, arch, False)

        if data_repo is None:
            package_path = Path(pkgname)

            if is_apk(package_path):
                paths.append(package_path)
                continue
            else:
                raise RuntimeError(f"Couldn't find APKINDEX data for {pkgname}!")

        base_aports, _ = pmb.build.get_apkbuild(pkgname)
        channel = pmb.config.pmaports.read_config(base_aports)["channel"]

        apk_file = f"{pkgname}-{data_repo.version}.apk"
        host_path = context.config.work / "packages" / channel / arch / apk_file

        # If none of the packages have dependencies then we can run apk with
        # --no-network to avoid spurious APKINDEX updates
        if data_repo.depends:
            install_offline = False

        if not host_path.is_file():
            to_build.append(pkgname)

        paths.append(host_path)

    if to_build:
        pmb.build.packages(context, to_build, arch, force=True)
        # Check all the packages actually got builts
        for path in paths:
            if not path.is_file():
                raise RuntimeError(f"The package '{pkgname}' could not be built")

    if copy_key:
        scp_abuild_key(user, host, port)

    ssh_install_apks(user, host, port, paths, install_offline, allow_untrusted)
