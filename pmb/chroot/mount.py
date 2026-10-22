# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path

import pmb.chroot.binfmt
import pmb.config
import pmb.helpers.mount
import pmb.helpers.run
import pmb.install.losetup
from pmb.core import Chroot
from pmb.core.chroot import ChrootType
from pmb.core.context import get_context
from pmb.core.pkgrepo import pkgrepo_default_path
from pmb.helpers import logging


def mount_chroot_image(chroot: Chroot) -> None:
    """
    Mount an IMAGE type chroot, to modify an existing rootfs image. This
    doesn't support split images yet!
    """
    # Make sure everything is nicely unmounted just to be super safe
    # this is definitely overkill
    pmb.chroot.shutdown()
    pmb.install.losetup.detach_all()

    chroot_native = Chroot.native()
    pmb.chroot.init(chroot_native)

    loopdev = pmb.install.losetup.mount(
        Path("/") / Path(chroot.name).relative_to(chroot_native.path)
    )
    pmb.helpers.mount.bind_file(loopdev, chroot_native / "dev/install")
    # Set up device mapper bits
    pmb.helpers.run.root(["kpartx", "-u", loopdev])
    chroot.path.mkdir(exist_ok=True)
    loopdev_basename = os.path.basename(loopdev)
    # # The name of the IMAGE chroot is the path to the rootfs image
    if Path(f"/dev/mapper/{loopdev_basename}p2").exists():
        pmb.helpers.run.root(["mount", f"/dev/mapper/{loopdev_basename}p2", chroot.path])
        pmb.helpers.run.root(["mount", f"/dev/mapper/{loopdev_basename}p1", chroot.path / "boot"])
    else:
        pmb.helpers.run.root(["mount", f"/dev/{loopdev_basename}", chroot.path])

    pmb.config.workdir.chroot_save_init(chroot)

    logging.info(f"({chroot}) mounted {chroot.name}")


def create_device_nodes(chroot: Chroot) -> None:
    """Create device nodes for null, zero, full, random, urandom in the chroot."""
    try:
        # Create all device nodes as specified in the config
        for dev in pmb.config.chroot_device_nodes:
            path = chroot / "dev" / str(dev[4])
            if not path.exists():
                pmb.helpers.run.root(
                    [
                        "mknod",
                        path,  # name
                        str(dev[1]),  # type
                        str(dev[2]),  # major
                        str(dev[3]),  # minor
                    ]
                )
                # chmod needs to be split from mknod to accommodate
                # for FreeBSD mknod not including -m
                pmb.helpers.run.root(
                    [
                        "chmod",
                        str(dev[0]),  # permissions
                        path,  # name
                    ]
                )

        # Verify major and minor numbers of created nodes
        for dev in pmb.config.chroot_device_nodes:
            path = chroot / "dev" / str(dev[4])
            stat_result = path.stat()
            rdev = stat_result.st_rdev
            if not os.major(rdev) == dev[2]:
                raise RuntimeError(f"Wrong major in {path}")
            if not os.minor(rdev) == dev[3]:
                raise RuntimeError(f"Wrong minor in {path}")

        # Verify /dev/zero reading and writing
        path = chroot / "dev/zero"
        with open(path, "r+b", 0) as handle:
            if not handle.write(bytes([0xFF])):
                raise RuntimeError(f"Write failed for {path}")
            if not handle.read(1) == bytes([0x00]):
                raise RuntimeError(f"Read failed for {path}")

    # On failure: Show filesystem-related error
    except Exception as e:
        logging.info(str(e) + "!")
        raise RuntimeError(f"Failed to create device nodes in the '{chroot}' chroot.") from e


def mount_dev_tmpfs(chroot: Chroot = Chroot.native()) -> None:
    """
    Mount tmpfs inside the chroot's dev folder to make sure we can create
    device nodes, even if the filesystem of the work folder does not support
    it.
    """
    # Do nothing when it is already mounted
    dev = chroot / "dev"
    if pmb.helpers.mount.ismount(dev):
        return

    # Create the $chroot/dev folder and mount tmpfs there
    pmb.helpers.run.root(["mkdir", "-p", dev])
    pmb.helpers.run.root(["mount", "-t", "tmpfs", "-o", "size=1M,noexec,dev", "tmpfs", dev])

    # Create /dev/{stdin,stdout,stderr}
    pmb.helpers.run.root(["ln", "-s", "/proc/self/fd/0", dev / "stdin"])
    pmb.helpers.run.root(["ln", "-s", "/proc/self/fd/1", dev / "stdout"])
    pmb.helpers.run.root(["ln", "-s", "/proc/self/fd/2", dev / "stderr"])

    # Create pts, shm folders and device nodes
    pmb.helpers.run.root(["mkdir", "-p", dev / "pts", dev / "shm"])
    pmb.helpers.run.root(
        ["mount", "-t", "tmpfs", "-o", "nodev,nosuid,noexec", "tmpfs", dev / "shm"]
    )

    # Mount devpts for PTY support
    pmb.helpers.run.root(["mount", "-t", "devpts", "-o", "ptmxmode=0666", "devpts", dev / "pts"])

    create_device_nodes(chroot)

    # Setup /dev/fd as a symlink
    pmb.helpers.run.root(["ln", "-sf", "/proc/self/fd", f"{dev}/"])


def mount(chroot: Chroot) -> None:
    if chroot.type == ChrootType.IMAGE and not pmb.mount.ismount(chroot.path):
        mount_chroot_image(chroot)

    # Mount tmpfs as the chroot's /dev
    mount_dev_tmpfs(chroot)

    # Get all mountpoints
    arch = chroot.arch
    channel = pmb.config.pmaports.read_config(pkgrepo_default_path())["channel"]
    mountpoints: dict[Path, Path] = {}
    for src_template, target_template in pmb.config.chroot_mount_bind.items():
        src_template = src_template.replace("$WORK", os.fspath(get_context().config.work))
        src_template = src_template.replace("$ARCH", str(arch))
        src_template = src_template.replace("$CHANNEL", channel)
        mountpoints[Path(src_template)] = Path(target_template)

    # Mount if necessary
    for source, target in mountpoints.items():
        target_outer = chroot / target
        if not pmb.helpers.mount.ismount(target_outer):
            pmb.helpers.mount.bind(source, target_outer)

    # Set up binfmt
    if not arch.cpu_emulation_required():
        return

    arch_qemu = arch.qemu_user()

    # mount --bind the qemu-user binary
    pmb.chroot.binfmt.register(arch)
    pmb.helpers.mount.bind_file(
        Chroot.native() / f"usr/bin/qemu-{arch_qemu}",
        chroot / f"usr/bin/qemu-{arch_qemu}-static",
        create_folders=True,
    )


def mount_native_into_foreign(chroot: Chroot) -> None:
    source = Chroot.native().path
    target = chroot / "native"
    pmb.helpers.mount.bind(source, target)

    musl = next(source.glob("lib/ld-musl-*.so.1")).name
    musl_link = chroot / "lib" / musl
    if not musl_link.is_symlink():
        pmb.helpers.run.root(["ln", "-s", "/native/lib/" + musl, musl_link])


def remove_mnt_pmbootstrap(chroot: Chroot) -> None:
    """
    Safely remove /mnt/pmbootstrap directories from the chroot, without
    running rm -r as root and potentially removing data inside the
    mountpoint in case it was still mounted (bug in pmbootstrap, or user
    ran pmbootstrap 2x in parallel). This is similar to running 'rm -r -d',
    but we don't assume that the host's rm has the -d flag (busybox does
    not).
    """
    mnt_dir = chroot / "mnt/pmbootstrap"

    if not mnt_dir.exists():
        return

    for path in [*mnt_dir.glob("*"), mnt_dir]:
        pmb.helpers.run.root(["rmdir", path])
