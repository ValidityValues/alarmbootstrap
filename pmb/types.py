# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import enum
import subprocess
from argparse import Namespace
from pathlib import Path
from typing import Literal, TypedDict

from pmb.core.apkindex import Apkindex
from pmb.core.arch import Arch
from pmb.core.chroot import Chroot


class CrossCompile(enum.Enum):
    # Cross compilation isn't needed for this package:
    # 1) Either because the arch we will build for is exactly the same as the
    #    native arch, or
    # 2) because CPU emulation is not needed (e.g. x86 on x86_64)
    UNNECESSARY = "unnecessary"
    # Cross compilation disabled, only use QEMU
    QEMU_ONLY = "qemu-only"
    # Cross compilation will use crossdirect
    CROSSDIRECT = "crossdirect"
    # Cross compilation will use cross-native
    CROSS_NATIVE = "cross-native"
    # Cross compilation will use cross-native2
    CROSS_NATIVE2 = "cross-native2"

    def __str__(self) -> str:
        return self.value

    def enabled(self) -> bool:
        """Are we cross-compiling for this value of cross?"""
        return self not in [CrossCompile.UNNECESSARY, CrossCompile.QEMU_ONLY]

    def host_chroot(self, arch: Arch) -> Chroot:
        """
        Chroot for the package target architecture (the "host" machine).
        Cross native (v1) is the exception, since we exclusively use the native
        chroot for that.
        """
        if arch == Arch.native():
            return Chroot.native()

        match self:
            case CrossCompile.CROSS_NATIVE:
                return Chroot.native()
            case _:
                return Chroot.buildroot(arch)

    def build_chroot(self, arch: Arch) -> Chroot:
        """Chroot for the package build architecture (the "build" machine)."""
        if arch == Arch.native():
            return Chroot.native()

        match self:
            case CrossCompile.UNNECESSARY | CrossCompile.CROSSDIRECT | CrossCompile.QEMU_ONLY:
                return Chroot.buildroot(arch)
            case CrossCompile.CROSS_NATIVE | CrossCompile.CROSS_NATIVE2:
                return Chroot.native()


class RunOutputTypeDefault(enum.Enum):
    LOG = enum.auto()
    STDOUT = enum.auto()
    INTERACTIVE = enum.auto()
    TUI = enum.auto()
    NULL = enum.auto()

    def is_to_stdout(self) -> bool:
        match self:
            case self.STDOUT | self.INTERACTIVE:
                return True
            case self.LOG | self.TUI | self.NULL:
                return False
            case _:
                raise AssertionError

    def has_timeout(self) -> bool:
        match self:
            case self.LOG | self.STDOUT:
                return True
            case self.INTERACTIVE | self.TUI | self.NULL:
                return False
            case _:
                raise AssertionError

    def has_pass_stdin(self) -> bool:
        match self:
            case self.INTERACTIVE | self.TUI:
                return True
            case self.LOG | self.STDOUT | self.NULL:
                return False
            case _:
                raise AssertionError

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def from_string(string: str) -> RunOutputTypeDefault:
        match string:
            case "log":
                return RunOutputTypeDefault.LOG
            case "stdout":
                return RunOutputTypeDefault.STDOUT
            case "interactive":
                return RunOutputTypeDefault.INTERACTIVE
            case "tui":
                return RunOutputTypeDefault.TUI
            case "null":
                return RunOutputTypeDefault.NULL
            case _:
                raise ValueError


class RunOutputTypePopen(enum.Enum):
    BACKGROUND = enum.auto()
    PIPE = enum.auto()

    def is_to_stdout(self) -> bool:
        return False

    def has_timeout(self) -> bool:
        return False

    def has_pass_stdin(self) -> bool:
        return False


class WithExtraRepos(enum.Enum):
    DEFAULT = enum.auto()
    ENABLED = enum.auto()
    DISABLED = enum.auto()


RunOutputType = RunOutputTypeDefault | RunOutputTypePopen
RunReturnType = str | int | subprocess.Popen[bytes]
PathString = Path | str
Env = dict[str, PathString]
ActionKConfig = Literal["check", "edit", "migrate", "generate"]

# These types are not definitive / API, they exist to describe the current
# state of things so that we can improve our type hinting coverage and make
# future refactoring efforts easier.


class PartitionLayout(TypedDict):
    prep: int | None
    kernel: int | None
    boot: int | None
    reserve: int | None
    root: int


class Bootimg(TypedDict):
    cmdline: str
    bootimg_qcdt: str
    bootimg_qcdt_type: str | None
    bootimg_qcdt_exynos_platform: str | None
    bootimg_qcdt_exynos_subtype: str | None
    dtb_offset: str | None
    dtb_second: str
    base: str
    kernel_offset: str
    ramdisk_offset: str
    second_offset: str
    tags_offset: str
    pagesize: str
    header_version: int | None
    mtk_label_kernel: str
    mtk_label_ramdisk: str


# Property list generated with:
# $ rg --vimgrep "((^|\s)args\.\w+)" --only-matching | cut -d"." -f3 | sort | uniq
class PmbArgs(Namespace):
    action_flasher: str
    action_initfs: str
    action_kconfig: ActionKConfig
    action_netboot: str
    action_test: str
    add: str
    all: bool
    all_git: bool
    all_stable: bool
    allow_untrusted: bool
    android_recovery_zip: bool
    apkindex_path: Apkindex
    aports: list[Path] | None
    arch: Arch | None
    as_root: bool
    assume_yes: bool
    auto: bool
    autoinstall: bool
    boot_size: str
    build_default_device_arch: str
    buildroot: str
    built: bool
    ccache: bool
    ccache_size: str
    changed: bool
    chroot_usb: bool
    cipher: str
    clear_log: bool
    cmdline: str
    command: str
    config: Path
    cross: bool
    details: bool
    details_to_stdout: bool
    deviceinfo_parse_kernel: str
    devices: str
    disk: Path | None
    dry: bool
    envkernel: bool
    export_folder: Path
    extra_space: str
    fast: bool
    file: str | None
    filesystem: str
    flash_method: str
    folder: str
    force: bool
    fork_alpine: bool
    fork_alpine_retain_branch: bool
    fragment: str
    full_disk_encryption: bool
    go_mod_cache: bool
    hook: str | None
    host: str
    host_qemu: bool
    http: bool
    ignore_depends: bool
    image_size: str | None
    image: bool
    install_base: bool
    install_blockdev: bool
    install_cgpt: bool
    install_key: bool
    install_local_pkgs: bool
    install_recommends: bool
    is_default_channel: str
    iter_time: str
    jobs: str
    kconfig_check_details: bool
    kernel: str
    keymap: str
    keep_going: bool
    lax: bool
    lines: int
    log: Path
    memory: int
    mirror_alpine: str
    mirror_postmarketos: str
    name: str | None
    nconfig: bool
    netboot: bool
    no_depends: bool
    no_fde: bool
    no_firewall: bool
    no_image: bool
    no_reboot: bool
    no_sshd: bool
    non_existing: str
    odin_flashable_tar: bool
    offline: bool
    output: RunOutputTypeDefault
    overview: bool
    # FIXME (#2324): figure out the args.package vs args.packages situation
    package: str | list[str]
    packages: list[str]
    partition: str
    password: str
    path: Path
    pkgname: str
    pkgname_pkgver_srcurl: str
    pkgs_local: bool
    pkgs_local_mismatch: bool
    pkgs_online_mismatch: bool
    port: int
    qemu_audio: str | None
    qemu_cpu: str | None
    qemu_display: str
    qemu_gl: bool
    qemu_kvm: bool
    qemu_tablet: bool
    recovery_flash_kernel: bool
    recovery_install_partition: str
    ref: str
    replace: bool
    repository: str
    reset: bool
    resume: bool
    rootfs: bool
    rsync: bool
    scripts: str
    second_storage: str | None
    sector_size: int | None
    selected_providers: dict[str, str]
    sparse: bool | None
    split: bool | None
    src: str
    ssh_keys: str
    strict: bool
    sudo_timer: bool
    suffix: str
    timeout: float | None
    user: str
    value: str | None
    verbose: bool
    verify: bool
    work: Path
    xauth: bool
    xconfig: bool
    zap: bool
