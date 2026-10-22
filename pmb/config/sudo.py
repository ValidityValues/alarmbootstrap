# Copyright 2023 Anjandev Momi
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import shutil
from functools import lru_cache


@lru_cache
def which_sudo() -> str | None:
    """
    Return a command required to run commands as root, if any.

    Find whether sudo, doas, or run0 is installed for commands that require root.
    Allows user to override preferred sudo with PMB_SUDO env variable.
    """
    if os.getuid() == 0:
        return None

    supported_sudos = ["doas", "sudo", "run0"]

    user_set_sudo = os.getenv("PMB_SUDO")
    if user_set_sudo is not None:
        if shutil.which(user_set_sudo) is None:
            raise RuntimeError(
                "PMB_SUDO environmental variable is set to"
                f" {user_set_sudo} but pmbootstrap cannot find"
                " this command on your system."
            )
        return user_set_sudo

    for sudo in supported_sudos:
        if shutil.which(sudo) is not None:
            return sudo

    raise RuntimeError(
        "Can't find sudo, doas, or run0 required to run pmbootstrap."
        " Please install sudo, doas, run0, or specify your own sudo"
        " with the PMB_SUDO environmental variable."
    )
