# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import sys
from pathlib import Path
from typing import Any, Final, TextIO

from pmb.meta import Cache

logfd: TextIO

CRITICAL: Final[int] = logging.CRITICAL
FATAL: Final[int] = logging.FATAL
ERROR: Final[int] = logging.ERROR
WARNING: Final[int] = logging.WARNING
WARN: Final[int] = logging.WARNING
INFO: Final[int] = logging.INFO
DEBUG: Final[int] = logging.DEBUG
NOTSET: Final[int] = logging.NOTSET
VERBOSE: Final[int] = 5


class LogHandler(logging.StreamHandler):
    """Write to stdout and to the already opened log file."""

    def __init__(self, details_to_stdout: bool = False, quiet: bool = False) -> None:
        super().__init__()
        self.details_to_stdout = details_to_stdout
        self.quiet = quiet

        # FIXME: importing pmb.config pulls in a whole lot of stuff
        # and can easily lead to circular imports, so we defer it until here.
        import pmb.config

        self.styles = pmb.config.styles

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)

            # INFO or higher: Write to stdout
            if self.details_to_stdout or (not self.quiet and record.levelno >= logging.INFO):
                stream = self.stream

                styles = self.styles

                msg_col = (
                    msg.replace(
                        "NOTE:",
                        f"{styles['BLUE']}NOTE:{styles['END']}",
                        1,
                    )
                    .replace(
                        "WARNING:",
                        f"{styles['YELLOW']}WARNING:{styles['END']}",
                        1,
                    )
                    .replace(
                        "ERROR:",
                        f"{styles['RED']}ERROR:{styles['END']}",
                        1,
                    )
                    .replace(
                        "DONE!",
                        f"{styles['GREEN']}DONE!{styles['END']}",
                        1,
                    )
                    .replace(
                        "*** ",
                        f"{styles['GREEN']}*** ",
                        1,
                    )
                )

                for key, value in styles.items():
                    msg_col = msg_col.replace(f"@{key}@", value)
                    # Strip from the normal log message
                    msg = msg.replace(f"@{key}@", "")

                msg_col += styles["END"]

                stream.write(msg_col)
                stream.write(self.terminator)
                self.flush()

            # Everything: Write to logfd
            if not self.details_to_stdout:
                msg = "(" + str(os.getpid()).zfill(6) + ") " + msg
                logfd.write(msg + "\n")
                logfd.flush()

        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            self.handleError(record)


def add_verbose_log_level() -> None:
    """
    Add a new log level "verbose", which is below "debug".

    Also monkeypatch logging, so it can be used with logging.verbose().

    This function is based on work by Voitek Zylinski and sleepycal:
    https://stackoverflow.com/a/20602183
    All stackoverflow user contributions are licensed as CC-BY-SA:
    https://creativecommons.org/licenses/by-sa/3.0/
    """
    logging.VERBOSE = VERBOSE  # type: ignore[attr-defined]
    logging.addLevelName(VERBOSE, "VERBOSE")
    logging.Logger.verbose = lambda inst, msg, *args, **kwargs: inst.log(  # type: ignore[attr-defined]
        VERBOSE, msg, *args, **kwargs
    )
    logging.verbose = lambda msg, *args, **kwargs: logging.log(VERBOSE, msg, *args, **kwargs)  # type: ignore[attr-defined]


def init(
    logfile: Path, verbose: bool, details_to_stdout: bool = False, quiet: bool = False
) -> None:
    """Set log format and add the log file descriptor to logfd, add the verbose log level."""
    global logfd

    if "logfs" in globals():
        warning("Logging already initialized, skipping...")
        return

    # Require containing directory to exist (so we don't create the work
    # folder and break the folder migration logic, which needs to set the
    # version upon creation)
    if not details_to_stdout and logfile.parent.exists():
        logfd = open(logfile, "a+")  # ruff:ignore[open-file-with-context-handler]
        logfd.write("\n\n")
    elif details_to_stdout:
        logfd = sys.stdout
    else:
        logfd = open(os.devnull, "w")  # ruff:ignore[open-file-with-context-handler]

    # Set log format
    root_logger = logging.getLogger()
    root_logger.handlers = []
    formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")

    # Set log level
    add_verbose_log_level()
    root_logger.setLevel(logging.DEBUG)
    if verbose:
        root_logger.setLevel(VERBOSE)

    # Add a custom log handler
    handler = LogHandler(details_to_stdout=details_to_stdout, quiet=quiet)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    if "--password" in sys.argv:
        sys.argv[sys.argv.index("--password") + 1] = "[REDACTED]"
    logging.debug(f"$ {' '.join(sys.argv)}")


def disable() -> None:
    logger = logging.getLogger()
    logger.disabled = True


# We have our own logging wrappers so we can make mypy happy
# by not calling the (undefined) logging.verbose() function.


def critical(msg: object, *args: object, **kwargs: Any) -> None:
    logging.critical(msg, *args, **kwargs)


def fatal(msg: object, *args: object, **kwargs: Any) -> None:
    logging.fatal(msg, *args, **kwargs)


def error(msg: object, *args: object, **kwargs: Any) -> None:
    logging.error(msg, *args, **kwargs)


def warning(msg: object, *args: object, **kwargs: Any) -> None:
    logging.warning(msg, *args, **kwargs)


@Cache("msg")
def warn_once(msg: str) -> None:
    logging.warning(msg)


def info(msg: object, *args: object, **kwargs: Any) -> None:
    logging.info(msg, *args, **kwargs)


def debug(msg: object, *args: object, **kwargs: Any) -> None:
    logging.debug(msg, *args, **kwargs)


def verbose(msg: object, *args: object, **kwargs: Any) -> None:
    logging.verbose(msg, *args, **kwargs)  # type: ignore[attr-defined]


def log(level: int, msg: object, *args: object, **kwargs: Any) -> None:
    logging.log(level, msg, *args, **kwargs)
