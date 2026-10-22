# Copyright 2024 Stefan "Newbyte" Hansson
# SPDX-License-Identifier: GPL-3.0-or-later


class BuildFailedError(Exception):
    """
    Exception to be raised when pmbootstrap fails to build a package. This is handled
    separately from NonBugError as it needs to be treated differently as we want to hint
    to users that they can check the log for more information when a build fails.
    """


class CommandFailedError(Exception):
    """
    Exception to be raised when a command pmbootstrap has launched via shell fails. Should only be
    handled on a selective basis.
    """


class NonBugError(Exception):
    """
    Exception which originates from a problem not caused by pmbootstrap's code. This
    could for example be raised if there is an error in a package pmbootstrap is
    interacting with in some way.
    """


class PackagingError(Exception):
    """
    Exception which at least very likely originates from a problem in the pmaports/aports packaging.
    This could for instance be due to a package specifying a path to a file that no longer exists or
    mkinitfs failing to run.
    """
