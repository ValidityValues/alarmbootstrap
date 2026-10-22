# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import time
from pathlib import Path

import pmb.helpers.pmaports
import pmb.helpers.run


def replace(path: Path, old: str, new: str) -> None:
    text = ""
    with path.open("r", encoding="utf-8") as handle:
        text = handle.read()

    text = text.replace(old, new)

    with path.open("w", encoding="utf-8") as handle:
        handle.write(text)


def replace_apkbuild(pkgname: str, key: str, new: int | str, in_quotes: bool = False) -> None:
    """
    Replace one key=value line in an APKBUILD and verify it afterwards.

    :param pkgname: package name, e.g. "hello-world"
    :param key: key that should be replaced, e.g. "pkgver"
    :param new: new value
    :param in_quotes: expect the value to be in quotation marks ("")
    """
    # Read old value
    path = pmb.helpers.pmaports.find(pkgname) / "APKBUILD"
    apkbuild = pmb.parse.apkbuild(path)
    old = apkbuild[key]

    # Prepare old/new strings
    if in_quotes:
        line_old = f'{key}="{old}"'
        line_new = f'{key}="{new}"'
    else:
        line_old = f"{key}={old}"
        line_new = f"{key}={new}"

    # Replace
    replace(path, "\n" + line_old + "\n", "\n" + line_new + "\n")

    # Verify
    pmb.parse.apkbuild.cache_clear()
    apkbuild = pmb.parse.apkbuild(path)
    if apkbuild[key] != str(new):
        raise RuntimeError(
            f"Failed to set '{key}' for pmaport '{pkgname}'. Make sure"
            f" that there's a line with exactly the string '{line_old}'"
            f" and nothing else in: {path}"
        )


def is_apk(path: Path) -> bool:
    return path.is_file() and path.suffix == ".apk"


def is_up_to_date(
    path_sources: list[Path], path_target: Path | None = None, lastmod_target: float | None = None
) -> bool:
    """
    Check if a file is up-to-date by comparing the last modified timestamps.

    (just like make does it).

    :param path_sources: list of full paths to the source files
    :param path_target: full path to the target file
    :param lastmod_target: the timestamp of the target file. specify this as
                           alternative to specifying path_target.
    """
    if path_target and lastmod_target:
        raise RuntimeError("Specify path_target *or* lastmod_target, not both!")

    lastmod_source = None
    for path_source in path_sources:
        lastmod = path_source.stat().st_mtime
        if not lastmod_source or lastmod > lastmod_source:
            lastmod_source = lastmod

    if path_target:
        lastmod_target = path_target.stat().st_mtime

    if lastmod_target is None or lastmod_source is None:
        raise AssertionError

    return lastmod_target >= lastmod_source


def is_older_than(path: Path, seconds: int) -> bool:
    """Check if a single file is older than a given amount of seconds."""
    if not path.exists():
        return True
    lastmod = path.stat().st_mtime
    return lastmod + seconds < time.time()


def symlink(file: Path, link: Path) -> None:
    """Check if the symlink is already present, otherwise create it."""
    if link.exists():
        if link.is_symlink() and link.readlink().resolve() == file.resolve():
            return
        raise RuntimeError(f"File exists: {link}")
    elif link.is_symlink():
        link.unlink()

    # Create the symlink
    pmb.helpers.run.user(["ln", "-s", file, link])


def wait_until_exists(file: Path) -> None:
    """
    Wait for the given file to appear and raise a RuntimeError if it didn't.
    The timeout is about 15s by default and can be adjusted with the
    environment variable PMB_FILE_WAIT_UNTIL_EXISTS_MAX.
    """
    if file.exists():
        return

    logging.debug(f"Waiting for file to appear: {file}")

    tries = int(os.getenv("PMB_FILE_WAIT_UNTIL_EXISTS_MAX", "150"))
    for _i in range(tries):
        if file.exists():
            return
        time.sleep(0.1)

    raise RuntimeError(f"File did not appear: {file}")
