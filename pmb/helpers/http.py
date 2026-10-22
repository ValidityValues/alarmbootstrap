# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import os
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Any, Literal, overload

import pmb.helpers.cli
import pmb.helpers.run
from pmb.core.context import get_context
from pmb.helpers import logging


def cache_file(prefix: str, url: str) -> Path:
    prefix = prefix.replace("/", "_")
    return Path(
        f"{prefix}_{hashlib.sha256(url.encode('utf-8'), usedforsecurity=False).hexdigest()}"
    )


@overload
def download(
    url: str,
    prefix: str,
    cache: bool = ...,
    loglevel: int = ...,
    allow_404: Literal[False] = ...,
    flush_progress_bar_on_404: bool = ...,
) -> Path: ...


@overload
def download(
    url: str,
    prefix: str,
    cache: bool = ...,
    loglevel: int = ...,
    allow_404: Literal[True] = ...,
    flush_progress_bar_on_404: bool = ...,
) -> Path | None: ...


def download(
    url: str,
    prefix: str,
    cache: bool = True,
    loglevel: int = logging.INFO,
    allow_404: bool = False,
    flush_progress_bar_on_404: bool = False,
) -> Path | None:
    """
    Download a file to disk.

    :param url: the http(s) address of to the file to download
    :param prefix: for the cache, to make it easier to find (cache files
        get a hash of the URL after the prefix)
    :param cache: if True, and url is cached, do not download it again
    :param loglevel: change to logging.DEBUG to only display the download
        message in 'pmbootstrap log', not in stdout.
        We use this when downloading many APKINDEX files at once, no
        point in showing a dozen messages.
    :param allow_404: do not raise an exception when the server responds with a 404 Not Found error.
        Only display a warning on stdout (no matter if loglevel is changed).
    :param flush_progress_bar_on_404: download happens while a progress bar is
        displayed, flush it before printing a warning for 404

    :returns: path to the downloaded file in the cache or None on 404
    """
    # Create cache folder
    context = get_context()
    if not os.path.exists(context.config.work / "cache_http"):
        pmb.helpers.run.user(["mkdir", "-p", context.config.work / "cache_http"])

    # Check if file exists in cache
    path = context.config.work / "cache_http" / cache_file(prefix, url)
    if os.path.exists(path):
        if cache:
            return path
        pmb.helpers.run.user(["rm", path])

    # Offline and not cached
    if context.offline:
        raise RuntimeError(f"File not found in cache and offline flag is enabled: {url}")

    # Download the file
    logging.log(loglevel, "Download " + url)
    try:
        with urllib.request.urlopen(url) as response, open(path, "wb") as handle:
            shutil.copyfileobj(response, handle)
    # Handle 404
    except urllib.error.HTTPError as e:
        if e.code == 404 and allow_404:
            if flush_progress_bar_on_404:
                pmb.helpers.cli.progress_flush()
            logging.warning("WARNING: file not found: " + url)
            return None
        raise

    # Return path in cache
    return path


@overload
def retrieve(
    url: str, headers: dict[str, str] | None = ..., allow_404: Literal[False] = ...
) -> str: ...


@overload
def retrieve(
    url: str, headers: dict[str, str] | None = ..., allow_404: Literal[True] = ...
) -> str | None: ...


def retrieve(
    url: str, headers: dict[str, str] | None = None, allow_404: bool = False
) -> str | None:
    """
    Fetch the content of a URL and returns it as string.

    :param url: the http(s) address of to the resource to fetch
    :param headers: dict of HTTP headers to use
    :param allow_404: do not raise an exception when the server responds with a
        404 Not Found error. Only display a warning

    :returns: str with the content of the response
    """
    # Download the file
    logging.verbose("Retrieving " + url)

    if headers is None:
        headers = {}

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return response.read()
    # Handle 404
    except urllib.error.HTTPError as e:
        if e.code == 404 and allow_404:
            logging.warning("WARNING: failed to retrieve content from: " + url)
            return None
        raise


def retrieve_json(url: str, headers: dict[str, str] | None = None) -> Any:
    """
    Fetch the contents of a URL, parse it as JSON and return it.

    See retrieve() for the meaning of the parameters.
    """
    return json.loads(retrieve(url, headers, False))


def measure_latency(url: str) -> float:
    """
    Requests a URL and returns the total time it took to perform the request.

    :param url: the http(s) address of the resource to fetch

    :returns: seconds it took to complete the request
    """
    req = urllib.request.Request(url)
    start_time = time.monotonic()
    with urllib.request.urlopen(req) as response:
        response.read()
    return time.monotonic() - start_time
