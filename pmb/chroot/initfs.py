# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pmb.chroot.apk
import pmb.chroot.initfs_hooks
import pmb.helpers.cli
from pmb.core import Chroot
from pmb.core.context import get_context
from pmb.helpers import logging
from pmb.helpers.exceptions import CommandFailedError, NonBugError, PackagingError
from pmb.parse.deviceinfo import Deviceinfo, InitfsCompressionFormat
from pmb.types import PathString, RunOutputTypeDefault


def build(chroot: Chroot) -> None:
    # Update mkinitfs and hooks
    pmb.chroot.apk.install(["postmarketos-mkinitfs"], chroot)
    pmb.chroot.initfs_hooks.update(chroot)

    # Call mkinitfs
    logging.info(f"({chroot}) mkinitfs")
    pmb.chroot.root(["mkinitfs"], chroot)


def extract(chroot: Chroot, deviceinfo: Deviceinfo, extra: bool = False) -> Path:
    """
    Extract the initramfs to /tmp/initfs-extracted or the initramfs-extra to
    /tmp/initfs-extra-extracted and return the outside extraction path.
    """
    # Extraction folder
    inside = Path("/tmp/initfs-extracted")
    initfs_file = Path("/boot/initramfs")

    if extra:
        inside = Path("/tmp/initfs-extra-extracted")
        initfs_file = initfs_file.with_name(f"{initfs_file.name}-extra")

    if not (chroot / initfs_file).exists():
        raise NonBugError("The initramfs needs to be generated first! Try 'pmbootstrap initfs'")

    outside = chroot / inside
    if outside.exists():
        if not pmb.helpers.cli.confirm(
            f"Extraction folder {outside} already exists. Do you want to overwrite it?"
        ):
            raise NonBugError("Aborted!")
        pmb.chroot.root(["rm", "-r", inside], chroot)

    # Extraction script (because passing a file to stdin is not allowed
    # in pmbootstrap's chroot/shell functions for security reasons)
    with (chroot / "tmp/_extract.sh").open("w") as handle:
        handle.write(f"#!/bin/sh\ncd {inside} && cpio -i < _initfs\n")

    decompress_cmd: PathString | None
    compress_extension: str

    match deviceinfo.initfs_compression.format_:
        case InitfsCompressionFormat.ZSTD:
            pmb.chroot.apk.install(["zstd"], chroot)
            decompress_cmd = "zstd"
            compress_extension = ".zst"
        case InitfsCompressionFormat.LZ4:
            # FIXME: Decompressing lz4 is weirdly tricky for some reason. Simply doing
            # `lz4 -d $FILENAME.lz4` followed by `cpio -i < $FILENAME` does not work and makes cpio
            # error out about not being able to read the cpio archive.
            #
            # After investigating it, I found that using `lz4 -d $FILENAME.lz4` along with the
            # aforementioned cpio invocation using GNU cpio instead of BusyBox cpio makes it go
            # further, but it still doesn't successfully unpack the cpio archive. Given that not a
            # single device in pmaports currently uses lz4 compression for its initramfs at the time
            # of writing, maybe it's just entirely broken.
            raise RuntimeError("LZ4 compression is not yet supported by the initramfs extractor")
        case InitfsCompressionFormat.LZMA:
            pmb.chroot.apk.install(["xz"], chroot)
            # For some reason, we actually get an XZ archive when the compression format is set to
            # LZMA.
            decompress_cmd = "xz"
            compress_extension = ".xz"
        case InitfsCompressionFormat.GZIP:
            decompress_cmd = "gzip"
            compress_extension = ".gz"
        case InitfsCompressionFormat.NONE:
            decompress_cmd = None
            compress_extension = ""

    # Extract
    commands: list[list[PathString]] = [
        ["mkdir", "-p", inside],
        ["cp", initfs_file, f"{inside}/_initfs{compress_extension}"],
        [decompress_cmd, "-d", f"{inside}/_initfs{compress_extension}"]
        if decompress_cmd
        else ["echo", "Skipping initramfs decompression as no decompressor was specified."],
        ["cat", "/tmp/_extract.sh"],  # for the log
        ["sh", "/tmp/_extract.sh"],
        ["rm", "/tmp/_extract.sh", f"{inside}/_initfs"],
    ]
    for command in commands:
        pmb.chroot.root(command, chroot)

    # Return outside path for logging
    return outside


def ls(suffix: Chroot, deviceinfo: Deviceinfo, extra: bool = False) -> None:
    tmp = "/tmp/initfs-extracted"
    if extra:
        tmp = "/tmp/initfs-extra-extracted"
    extract(suffix, deviceinfo, extra)
    pmb.chroot.root(["ls", "-lahR", "."], suffix, Path(tmp), RunOutputTypeDefault.STDOUT)
    pmb.chroot.root(["rm", "-r", tmp], suffix)


def frontend(action: str, hook: str | None) -> None:
    context = get_context()
    chroot = Chroot.rootfs(context.config.device)
    deviceinfo = pmb.parse.deviceinfo()

    match action:
        case "hook_ls":
            pmb.chroot.initfs_hooks.ls(chroot)
        case "hook_add" | "hook_del":
            if hook is None:
                raise AssertionError

            match action:
                case "hook_add":
                    pmb.chroot.initfs_hooks.add(hook, chroot)
                case "hook_del":
                    pmb.chroot.initfs_hooks.delete(hook, chroot)
                case _:
                    raise AssertionError("Unreachable")
        case "extract":
            dir = extract(chroot, deviceinfo)
            logging.info(f"Successfully extracted initramfs to: {dir}")
            if deviceinfo.create_initfs_extra:
                dir_extra = extract(chroot, deviceinfo, True)
                logging.info(f"Successfully extracted initramfs-extra to: {dir_extra}")
        case "ls":
            logging.info("*** initramfs ***")
            ls(chroot, deviceinfo)
            if deviceinfo.create_initfs_extra:
                logging.info("*** initramfs-extra ***")
                ls(chroot, deviceinfo, True)
        case "build" | _:
            build(chroot)

    if action in ["hook_add", "hook_del"]:
        # Rebuild the initfs after adding/removing a hook
        try:
            build(chroot)
        except CommandFailedError as exception:
            raise PackagingError("Failed to rebuild initramfs. Broken hook?") from exception

    if action in ["ls", "extract"]:
        link = "https://wiki.postmarketos.org/wiki/Initramfs_development"
        logging.info(f"See also: <{link}>")
