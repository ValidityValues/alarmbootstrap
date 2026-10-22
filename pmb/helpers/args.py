# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import sys

import pmb.config
import pmb.helpers.git
from pmb.core.context import CommandTimeout, Context, TimeoutReason
from pmb.core.pkgrepo import pkgrepo_default_path
from pmb.types import PmbArgs

"""This file constructs the args variable, which is passed to almost all
   functions in the pmbootstrap code base. Here's a listing of the kind of
   information it stores.

    1. Argparse
       Variables directly from command line argument parsing (see
       pmb/parse/arguments.py, the "dest" parameter of the add_argument()
       calls defines where it is stored in args).

       Examples:
       args.action ("zap", "chroot", "build" etc.)
       args.as_root (True when --as-root is passed)
       ...

    2. Argparse merged with others
       Variables from the user's config file (~/.config/pmbootstrap_v3.cfg) that
       can be overridden from the command line (pmb/parse/arguments.py) and
       fall back to the defaults defined in pmb/config/__init__.py (see
       "defaults = {..."). The user's config file gets generated interactively
        with "pmbootstrap init".

       Examples:
       args.aports ("$WORK/cache_git/pmaports", override with --aports)
       args.device ("samsung-i9100", "qemu-amd64" etc.)
       get_context().config.work ("/home/user/.local/var/pmbootstrap", override with --work)

    3. Parsed configs
       Similar to the cache above, specific config files get parsed and added
       to args, so they can get accessed quickly (without parsing the configs
       over and over). These configs are not only used in one specific
       location, so having a short name for them increases readability of the
       code as well.

       Examples:
       deviceinfo (e.g. {"name": "Mydevice", "arch": "armhf", ...})
"""


def init(args: PmbArgs) -> PmbArgs:
    args_ = PmbArgs()
    # Basic initialization
    # print(json.dumps(args.__dict__))
    # sys.exit(0)
    config = pmb.config.load(args.config)

    if args.aports:
        for pmaports_dir in args.aports:
            if pmaports_dir.exists():
                continue
            raise ValueError(
                f"pmaports path (specified with --aports) does not exist: {pmaports_dir}"
            )

    # Override config at runtime with command line arguments
    for key in vars(config):
        if key.startswith("_") or key == "user":
            continue
        value = getattr(args, key, None)
        if value:
            setattr(config, key, value)

        # Deny accessing the attribute via args
        if hasattr(args, key):
            delattr(args, key)

    running_in_ci = os.environ.get("CI")

    # Configure runtime context
    context = Context(config)
    # Only enable the timeout by default in CI.
    if running_in_ci and args.timeout is None:
        context.command_timeout = CommandTimeout(length=900, reason=TimeoutReason.CI_DETECTED)
    elif args.timeout is not None:
        context.command_timeout = CommandTimeout(
            length=args.timeout, reason=TimeoutReason.TIMEOUT_ARG
        )
    context.details_to_stdout = args.details_to_stdout
    context.quiet = args.quiet
    context.offline = args.offline
    context.command = args.action
    context.cross = args.cross
    context.ccache = args.ccache
    context.assume_yes = getattr(args, "assume_yes", False)
    context.force = getattr(args, "force", False)
    context.no_depends = getattr(args, "no_depends", False)

    # Initialize context
    pmb.core.context.set_context(context)

    # Initialize logs (we could raise errors below)
    pmb.helpers.logging.init(context.log, args.verbose, context.details_to_stdout, args.quiet)
    pmb.helpers.logging.debug(f"pmbootstrap v{pmb.__version__} (Python {sys.version})")

    if context.command_timeout:
        pmb.helpers.logging.info(
            f"NOTE: Timeout enabled, commands will be killed after {context.command_timeout.length} seconds of not writing any output. Reason: {context.command_timeout.reason}"
        )

    # Initialization code which may raise errors
    if args.action not in [
        "init",
        "checksum",
        "config",
        "bootimg_analyze",
        "log",
        "pull",
        "shutdown",
        "zap",
    ]:
        pmb.config.pmaports.read_config()
        pmb.helpers.git.parse_channels_cfg(pkgrepo_default_path())

    # Remove attributes from args so they don't get used by mistake
    if hasattr(args, "timeout"):
        del args.timeout
    del args.details_to_stdout
    del args.log
    del args.quiet
    del args.offline
    if hasattr(args, "force"):
        del args.force
    if hasattr(args, "device"):
        del args.device

    # Copy all properties from args to out that don't start with underscores
    for key, value in vars(args).items():
        if not key.startswith("_") and key != "from_argparse":
            setattr(args_, key, value)

    return args_
