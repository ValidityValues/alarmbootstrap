# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
# PYTHON_ARGCOMPLETE_OK
import os
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from pmb.helpers.exceptions import BuildFailedError, NonBugError, PackagingError

if TYPE_CHECKING:
    from pmb.types import PmbArgs

from . import config, parse
from .commands import run_command
from .commands.status import print_status
from .config import (
    init as config_init,
    require_programs,
)
from .core import Chroot, Config
from .core.context import get_context
from .helpers import logging, mount, other

# pmbootstrap version
__version__ = "3.12.1"

# Python version check
# === CHECKLIST FOR UPGRADING THE REQUIRED PYTHON VERSION ===
# * .ci/vermin.sh
# * README.md
# * docs/usage.rst
# * pmb/__init__.py (you are here)
# * pyproject.toml
# * when upgrading to python 3.11: pmb/helpers/toml.py and remove this line
version = sys.version_info
if version < (3, 10):
    print("You need at least Python 3.10 to run pmbootstrap")
    print("(You are running it with Python " + str(version.major) + "." + str(version.minor) + ")")
    sys.exit()


def print_log_hint() -> None:
    context = get_context(allow_failure=True)
    if context and context.details_to_stdout:
        return
    log = context.log if context else Config().work / "log.txt"
    # Hints about the log file (print to stdout only)
    log_hint = "Run 'pmbootstrap log' for details."
    if not os.path.exists(log):
        log_hint += (
            " Alternatively you can use '--details-to-stdout' to get more"
            " output, e.g. 'pmbootstrap --details-to-stdout init'."
        )
    print()
    print(log_hint)


def main() -> int:
    # Wrap everything to display nice error messages

    args: PmbArgs
    try:
        # Parse arguments, set up logging
        args = parse.arguments()
        context = get_context()
        os.umask(0o22)

        # Store script invocation command
        os.environ["PMBOOTSTRAP_CMD"] = sys.argv[0]

        # Sanity checks
        other.check_grsec()
        if not args.as_root and os.geteuid() == 0:
            raise NonBugError(
                "Do not run pmbootstrap as root!\n"
                "If you absolutely must run it as root, use 'pmbootstrap --as-root'"
            )

        # Check for required programs (and find their absolute paths)
        require_programs()

        # Initialize or require config
        if args.action == "init":
            config_init.frontend(args)
            return 0
        elif not os.path.exists(args.config):
            if args.config != config.defaults["config"]:
                raise NonBugError(f"Couldn't find file passed with --config: {args.config}")
            old_config = (
                Path(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"))
                / "pmbootstrap.cfg"
            )
            if os.path.exists(old_config):
                raise NonBugError(
                    f"Thanks for upgrading to pmbootstrap {__version__}!"
                    " The config file format has changed, please generate a new config with"
                    " 'pmbootstrap init'."
                )
            raise NonBugError(
                "Run 'pmbootstrap init' first to generate a config file (or use --config)."
            )
        elif not os.path.exists(context.config.work):
            raise NonBugError("Work path not found, please run 'pmbootstrap init' to create it.")

        # Migrate work folder if necessary
        if args.action not in ["shutdown", "zap", "log"]:
            other.migrate_work_folder()

        # Run the function with the action's name (in pmb/helpers/frontend.py)
        if args.action:
            run_command(args)
        else:
            logging.info("Run pmbootstrap -h for usage information.")

        # Still active notice
        if mount.ismount(Chroot.native() / "dev"):
            logging.info("NOTE: chroot is still active (use 'pmbootstrap shutdown' as necessary)")
        logging.info("DONE!")

    except KeyboardInterrupt:
        print("\nCaught KeyboardInterrupt, exiting …")
        sys.exit(130)  # SIGINT(2) + 128

    except NonBugError as exception:
        logging.error(f"ERROR: {exception}")
        return 2

    except BuildFailedError as exception:
        logging.error(f"ERROR: {exception}")
        print_log_hint()
        return 3

    except PackagingError as exception:
        logging.error(f"ERROR: {exception}")
        print_log_hint()
        print("""
This error likely originates from a packaging issue. Please ensure that your
local pmaports clone is up-to-date with 'pmbootstrap pull'. If the issue still
persists, try zapping all chroots with 'pmbootstrap zap --all' and try again.

Should that still not work, please open an issue in the pmaports (not
pmbootstrap) issue tracker including the pmbootstrap log.""")
        return 4

    except Exception as e:
        # Dump log to stdout when args (and therefore logging) init failed
        can_print_status = get_context(allow_failure=True) is not None
        if "args" not in locals():
            import logging as pylogging

            pylogging.getLogger().setLevel(logging.DEBUG)
            can_print_status = False

        logging.info("ERROR: " + str(e))
        logging.info("See also: <https://postmarketos.org/troubleshooting>")
        logging.debug(traceback.format_exc())

        print_log_hint()
        print(f"""
Before you report this error, ensure that pmbootstrap is up to date.
Find the latest version here: https://gitlab.postmarketos.org/postmarketOS/pmbootstrap/-/tags
Your version: {__version__}""")
        if can_print_status:
            print_status()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
