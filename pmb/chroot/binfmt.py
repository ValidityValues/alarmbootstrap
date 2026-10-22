# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os

import pmb.chroot.apk
import pmb.helpers.other
import pmb.helpers.run
import pmb.parse
from pmb.core.arch import Arch
from pmb.core.chroot import Chroot
from pmb.helpers import logging


def is_registered(arch_qemu: str | Arch) -> bool:
    return os.path.exists(f"/proc/sys/fs/binfmt_misc/qemu-{arch_qemu}")


def register(arch: Arch) -> None:
    """Get arch, magic, mask."""
    arch_qemu = arch.qemu_user()
    chroot = Chroot.native()

    # always make sure the qemu-<arch> binary is installed, since registering
    # may happen outside of this method (e.g. by OS)
    if f"qemu-{arch_qemu}" not in pmb.chroot.apk.installed(chroot):
        pmb.chroot.init(chroot)
        pmb.chroot.apk.install(["qemu-" + arch_qemu], chroot)

    if is_registered(arch_qemu):
        return
    pmb.helpers.other.check_binfmt_misc()

    # Don't continue if the actions from check_binfmt_misc caused the OS to
    # automatically register the target arch
    if is_registered(arch_qemu):
        return

    info = pmb.parse.binfmt_info(arch_qemu)

    # Build registration string
    # https://en.wikipedia.org/wiki/Binfmt_misc
    # :name:type:offset:magic:mask:interpreter:flags
    name = "qemu-" + arch_qemu
    type = "M"
    offset = ""
    magic = info["magic"]
    mask = info["mask"]
    interpreter = "/usr/bin/qemu-" + arch_qemu + "-static"
    flags = "C"
    code = ":".join(["", name, type, offset, magic, mask, interpreter, flags])

    # Register in binfmt_misc
    logging.info("Register qemu binfmt (" + arch_qemu + ")")
    register = "/proc/sys/fs/binfmt_misc/register"
    pmb.helpers.run.root(["sh", "-c", 'echo "' + code + '" > ' + register])


def unregister(arch: Arch) -> None:
    arch_qemu = arch.qemu_user()
    binfmt_file = "/proc/sys/fs/binfmt_misc/qemu-" + arch_qemu
    if not os.path.exists(binfmt_file):
        return
    logging.info("Unregister qemu binfmt (" + arch_qemu + ")")
    pmb.helpers.run.root(["sh", "-c", "echo -1 > " + binfmt_file])
