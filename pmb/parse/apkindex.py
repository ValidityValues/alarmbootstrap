# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import collections
from typing import Literal, cast, overload

import pmb.helpers.package
import pmb.helpers.repo
import pmb.parse.version
from pmb.core.apk_package import ApkPackage
from pmb.core.apkindex import Apkindex
from pmb.core.arch import Arch
from pmb.helpers import logging


@overload
def parse_add_block(
    ret: dict[str, ApkPackage],
    block: ApkPackage,
    provide: str | None = ...,
    multiple_providers: Literal[False] = ...,
) -> None: ...


@overload
def parse_add_block(
    ret: dict[str, dict[str, ApkPackage]],
    block: ApkPackage,
    provide: str | None = ...,
    multiple_providers: Literal[True] = ...,
) -> None: ...


@overload
def parse_add_block(
    ret: dict[str, ApkPackage] | dict[str, dict[str, ApkPackage]],
    block: ApkPackage,
    provide: str | None = ...,
    multiple_providers: bool = ...,
) -> None: ...


def parse_add_block(
    ret: dict[str, ApkPackage] | dict[str, dict[str, ApkPackage]],
    block: ApkPackage,
    provide: str | None = None,
    multiple_providers: bool = True,
) -> None:
    """
    Add one block to the return dictionary of parse().

    :param ret: dictionary of all packages in the APKINDEX that is
                getting built right now. This function will extend it.
    :param block: an ApkPackage to potentially add to ret.
    :param provide: defaults to the pkgname, could be a provide from the
                    "provides" list.
    :param multiple_providers: assume that there are more than one provider for
                               the package. This makes sense when parsing the
                               APKINDEX files from a repository (#1122), but
                               not when parsing apk's installed packages DB.
    """
    # Defaults
    pkgname = block.pkgname
    provide = provide or pkgname

    # Get an existing block with the same provide
    block_old = None
    if multiple_providers:
        ret = cast(dict[str, dict[str, ApkPackage]], ret)
        if provide in ret and pkgname in ret[provide]:
            picked_provides = ret[provide]
            if not isinstance(picked_provides, dict):
                raise AssertionError
            block_old = picked_provides[pkgname]
    else:
        if provide in ret:
            ret = cast(dict[str, ApkPackage], ret)
            picked_provide = ret[provide]
            if not isinstance(picked_provide, ApkPackage):
                raise AssertionError
            block_old = picked_provide

    # Ignore the block, if the block we already have has a higher version
    if block_old:
        version_old = block_old.version
        version_new = block.version
        if pmb.parse.version.compare(version_old, version_new) == 1:
            return

    # Add it to the result set
    if multiple_providers:
        ret = cast(dict[str, dict[str, ApkPackage]], ret)
        if provide not in ret:
            ret[provide] = {}
        picked_provides = ret[provide]
        picked_provides[pkgname] = block
    else:
        ret = cast(dict[str, ApkPackage], ret)
        ret[provide] = block


@overload
def parse(index: Apkindex) -> dict[str, dict[str, ApkPackage]]: ...


@overload
def parse(index: Apkindex, multiple_providers: Literal[False] = ...) -> dict[str, ApkPackage]: ...


@overload
def parse(
    index: Apkindex, multiple_providers: Literal[True] = ...
) -> dict[str, dict[str, ApkPackage]]: ...


def parse(
    index: Apkindex, multiple_providers: bool = True
) -> dict[str, ApkPackage] | dict[str, dict[str, ApkPackage]]:
    r"""
    Parse an APKINDEX.tar.gz file, and return its content as dictionary.

    :param index: APKINDEX.tar.gz file or apk package database
                 (almost the same format, but not compressed).
    :param multiple_providers: assume that there are more than one provider for
                               the package. This makes sense when parsing the
                               APKINDEX files from a repository (#1122), but
                               not when parsing apk's installed packages DB.
    :returns: (without multiple_providers)

    Generic format:
        ``{ pkgname: ApkPackage, ... }``

    Example:
        ``{ "postmarketos-mkinitfs": ApkPackage, "so:libGL.so.1": ApkPackage, ...}``

    :returns: (with multiple_providers)

    Generic format:
        ``{ provide: { pkgname: ApkPackage, ... }, ... }``

    Example:
        ``{ "postmarketos-mkinitfs": {"postmarketos-mkinitfs": ApkPackage},"so:libGL.so.1": {"mesa-egl": ApkPackage, "libhybris": ApkPackage}, ...}``
    """
    # Require the file to exist
    if not index.is_file():
        logging.verbose(
            "NOTE: APKINDEX not found, assuming no binary packages"
            f" exist for that architecture: {index}"
        )
        return {}

    # Try to get a cached result first
    lastmod = index.lstat().st_mtime
    cache_key_ = "multiple" if multiple_providers else "single"
    key = cache_key(index)
    if key in pmb.helpers.other.cache["apkindex"]:
        cache = pmb.helpers.other.cache["apkindex"][key]
        if cache["lastmod"] == lastmod:
            if cache_key_ in cache:
                return cache[cache_key_]
        else:
            clear_cache(index)

    block_lines = index.read_lines()

    # The APKINDEX might be empty, for example if you run "pmbootstrap index" and have no local
    # packages
    if not block_lines:
        return {}

    # Parse the whole APKINDEX file
    ret: dict[str, ApkPackage] = collections.OrderedDict()

    for block_line in block_lines:
        block_line = block_line.strip()
        if len(block_line) == 0:
            continue
        block = ApkPackage.from_apkindex_block(block_line.splitlines())
        # Skip virtual packages
        if block.timestamp is None:
            logging.verbose(f"Skipped virtual package {block} in file: {index}")
            continue

        # Add the next package and all provides
        parse_add_block(ret, block, None, multiple_providers)
        for provide in block.provides:
            parse_add_block(ret, block, provide, multiple_providers)

    # Update the cache
    key = cache_key(index)
    if key not in pmb.helpers.other.cache["apkindex"]:
        pmb.helpers.other.cache["apkindex"][key] = {"lastmod": lastmod}
    pmb.helpers.other.cache["apkindex"][key][cache_key_] = ret
    return ret


# FIXME: come up with something better here...
def cache_key(index: Apkindex) -> int:
    return hash(index)


def clear_cache(index: Apkindex) -> bool:
    """
    Clear the APKINDEX parsing cache.

    :returns: True on successful deletion, False otherwise
    """
    key = cache_key(index)
    logging.verbose(f"Clear APKINDEX cache for: {key}")
    if key in pmb.helpers.other.cache["apkindex"]:
        del pmb.helpers.other.cache["apkindex"][key]
        return True
    else:
        logging.verbose(
            "Nothing to do, index was not in cache:"
            + str(pmb.helpers.other.cache["apkindex"].keys())
        )
        return False


def providers(
    package: str,
    indexes: list[Apkindex],
    must_exist: bool = True,
) -> dict[str, ApkPackage]:
    """
    Get all packages, which provide one package.

    :param package: of which you want to have the providers
    :param indexes: list of APKINDEX.tar.gz files
    :param must_exist: When set to true, raise an exception when the package is
                       not provided at all.
    :returns: list of parsed packages. Example for package="so:libGL.so.1":
        ``{"mesa-egl": ApkPackage, "libhybris": ApkPackage}``
    """
    pkgname_with_op = package
    package = pmb.helpers.package.remove_operators(pkgname_with_op)

    ret: dict[str, ApkPackage] = collections.OrderedDict()
    for index in indexes:
        # Skip indexes not providing the package
        index_packages = parse(index)
        if package not in index_packages:
            continue

        indexed_package = index_packages[package]

        # Iterate over found providers
        for provider_pkgname, provider in indexed_package.items():
            version = provider.version
            if not pmb.helpers.package.check_version_constraints(pkgname_with_op, version):
                continue
            # Skip lower versions of providers we already found
            if provider_pkgname in ret:
                version_last = ret[provider_pkgname].version
                if pmb.parse.version.compare(version, version_last) == -1:
                    logging.verbose(
                        f"{package}: provided by: {provider_pkgname}-{version}"
                        f"in {index} (but {version_last} is higher)"
                    )
                    continue

            # Add the provider to ret
            logging.verbose(f"{package}: provided by: {provider_pkgname}-{version} in {index}")
            ret[provider_pkgname] = provider

    if ret == {} and must_exist:
        import os

        logging.debug(f"Searched in APKINDEX files: {', '.join([os.fspath(x) for x in indexes])}")
        raise RuntimeError("Could not find package '" + package + "'!")

    return ret


def _provider_highest_priority(
    providers: dict[str, ApkPackage], pkgname: str
) -> dict[str, ApkPackage]:
    """
    Get the provider(s) with the highest provider_priority and log a message.

    :param providers: returned dict from providers(), must not be empty
    :param pkgname: the package name we are interested in (for the log message)
    """
    max_priority = 0
    priority_providers: collections.OrderedDict[str, ApkPackage] = collections.OrderedDict()
    for provider_name, provider in providers.items():
        priority = int(-1 if provider.provider_priority is None else provider.provider_priority)
        if priority > max_priority:
            priority_providers.clear()
            max_priority = priority
        if priority == max_priority:
            priority_providers[provider_name] = provider

    if priority_providers:
        logging.debug(
            f"{pkgname}: picked provider(s) with highest priority "
            f"{max_priority}: {', '.join(priority_providers.keys())}"
        )
        return priority_providers

    # None of the providers seems to have a provider_priority defined
    return providers


def _provider_shortest(providers: dict[str, ApkPackage], pkgname: str) -> ApkPackage:
    """
    Get the provider with the shortest pkgname and log a message. In most cases
    this should be sufficient, e.g. 'mesa-purism-gc7000-egl, mesa-egl' or
    'gtk+2.0-maemo, gtk+2.0'.

    :param providers: returned dict from providers(), must not be empty
    :param pkgname: the package name we are interested in (for the log message)
    """
    ret = min(list(providers.keys()), key=len)
    if len(providers) != 1:
        logging.debug(
            f"{pkgname}: has multiple providers ("
            f"{', '.join(providers.keys())}), picked shortest: {ret}"
        )
    return providers[ret]


@overload
def package(
    package: str,
    arch: Arch,
    must_exist: Literal[True] = ...,
    indexes: list[Apkindex] | None = ...,
    user_repository: bool = ...,
) -> ApkPackage: ...


@overload
def package(
    package: str,
    arch: Arch,
    must_exist: bool = ...,
    indexes: list[Apkindex] | None = ...,
    user_repository: bool = ...,
) -> ApkPackage | None: ...


# This can't be cached because the APKINDEX can change during pmbootstrap build!
def package(
    package: str,
    arch: Arch,
    must_exist: bool = True,
    indexes: list[Apkindex] | None = None,
    user_repository: bool = True,
) -> ApkPackage | None:
    """
    Get a specific package's data from an apkindex.

    :param package: of which you want to have the apkindex data
    :param arch: defaults to native arch, only relevant for indexes=None
    :param must_exist: When set to true, raise an exception when the package is
                       not provided at all.
    :param indexes: list of APKINDEX.tar.gz, defaults to all index files
                    (depending on arch)
    :param user_repository: add path to index of locally built packages
    :returns: ApkPackage or None when the package was not found.
    """
    if not indexes:
        indexes = pmb.helpers.repo.apkindex_files(arch, user_repository=user_repository)
    # Provider with the same package
    package_providers = providers(package, indexes, must_exist)

    if package_providers:
        providers_priority = _provider_highest_priority(package_providers, package)
        num_providers = len(providers_priority)
        # Only one provider with max priority: return it
        if num_providers == 1:
            return next(iter(providers_priority.values()))
        # Multiple providers with max priority: let follow-on logic decide
        elif num_providers > 1:
            package_providers = providers_priority

    # Any provider
    if package_providers:
        return _provider_shortest(package_providers, package)

    # No provider
    if must_exist:
        raise RuntimeError("Package '" + package + "' not found in any APKINDEX.")
    return None
