# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import ctypes
import enum
import platform
from collections.abc import Sequence
from itertools import islice
from pathlib import Path, PosixPath, PurePosixPath

import pmb.config

# Initialised at the bottom
_cached_native_arch: Arch

# https://github.com/torvalds/linux/blob/d4b779985a6c853be5693fa6e8994034f8492abc/include/uapi/linux/personality.h#L56
PER_LINUX32 = 0x0008


def cpu_is_32_bit_capable() -> bool:
    """
    Check whether the host CPU is capable of executing 32-bit binaries.

    This is done by calling personality(PER_LINUX32), similar to how
    util-linux does it
    """
    # https://github.com/util-linux/util-linux/blob/15de47b9c955b9e3451d864e16dd646169316331/sys-utils/lscpu-cputype.c#L714
    personality = ctypes.CDLL(None).personality
    personality.restype = ctypes.c_int
    personality.argtypes = [ctypes.c_ulong]
    # personality sets the process execution domain, so we need to revert it immediately
    # if it succeeded. It returns the old process execution domain.
    result = personality(PER_LINUX32)

    if result == -1:
        return False
    else:
        personality(result)
        return True


def cp15_barriers_supported() -> bool:
    """
    Check whether the kernel is configured to emulate or execute cp15 barriers
    in hardware for aarch32.
    """
    sysctl_path = Path("/proc/sys/abi/cp15_barrier")
    # The path only exists if the kernel is configured with
    # CONFIG_ARMV8_DEPRECATED=y and CONFIG_CP15_BARRIER_EMULATION=y
    # A value of 1 means emulation, 2 is execution in hardware
    return sysctl_path.exists() and int(sysctl_path.read_text()) >= 1


class Arch(enum.Enum):
    """
    Supported architectures according to the Alpine
    APKBUILD format.
    """

    x86 = "x86"
    x86_64 = "x86_64"
    armhf = "armhf"
    armv7 = "armv7"
    aarch64 = "aarch64"
    riscv64 = "riscv64"
    s390x = "s390x"
    ppc64le = "ppc64le"
    # Arches Alpine can build for
    armel = "armel"
    loongarch32 = "loongarch32"
    loongarchx32 = "loongarchx32"
    loongarch64 = "loongarch64"
    mips = "mips"
    mips64 = "mips64"
    mipsel = "mipsel"
    mips64el = "mips64el"
    noarch = "noarch"
    ppc = "ppc"
    ppc64 = "ppc64"
    riscv32 = "riscv32"

    def __str__(self) -> str:
        return self.value

    @staticmethod
    def from_str(arch: str) -> Arch:
        try:
            return Arch(arch)
        except ValueError as exception:
            raise ValueError(
                f"Invalid architecture: '{arch}',"
                " expected something like:"
                f" {', '.join(sorted(str(a) for a in Arch.supported()))}"
            ) from exception

    @staticmethod
    def from_machine_type(machine_type: str) -> Arch:
        match machine_type:
            case "i686":
                return Arch.x86
            case "x86_64":
                return Arch.x86_64
            case "aarch64":
                return Arch.aarch64
            case "armv6l":
                return Arch.armhf
            case "armv7l" | "armv8l":
                return Arch.armv7
            case "ppc64le":
                return Arch.ppc64le
            case "loongarch64":
                return Arch.loongarch64
            case "riscv64":
                return Arch.riscv64
            case _:
                raise ValueError(f"Unsupported machine type '{machine_type}'")

    @staticmethod
    def from_arch_field(arch_field: Sequence[str]) -> set[Arch]:
        if len(arch_field) == 0:
            return set()

        match arch_field[0]:
            case "all" | "noarch":
                supported_arches = set(Arch)
                start = 1
            case _:
                supported_arches = set()
                start = 0

        for entry in islice(arch_field, start, None):
            if entry[0] == "!":
                arch = Arch.from_str(entry[1:])
                supported_arches.discard(arch)
            else:
                arch = Arch.from_str(entry)
                supported_arches.add(arch)

        return supported_arches

    @staticmethod
    def native() -> Arch:
        return _cached_native_arch

    def is_native(self) -> bool:
        return self == Arch.native()

    @staticmethod
    def supported() -> set[Arch]:
        """
        Officially supported host/target architectures for postmarketOS. Only
        specify architectures supported by Alpine here. For cross-compiling,
        we need to generate the "musl-$ARCH" and "gcc-$ARCH" packages (use
        "pmbootstrap aportgen musl-armhf" etc.).
        """
        return {
            Arch.armhf,
            Arch.armv7,
            Arch.aarch64,
            Arch.x86_64,
            Arch.x86,
            Arch.riscv64,
            Arch.s390x,
            Arch.ppc64le,
            Arch.loongarch64,
            Arch.native(),
        }

    @staticmethod
    def supported_binary() -> set[Arch]:
        """Officially supported architectures that have a binary repository"""
        pmaports_cfg = pmb.config.pmaports.read_config()
        return {Arch.from_str(i) for i in pmaports_cfg["supported_arches"].split(",")}

    def kernel_dir(self) -> str:
        """
        Name of the architecture-specific directory in the Linux kernel
        (in arch/).
        """
        match self:
            case Arch.x86 | Arch.x86_64:
                return "x86"
            case Arch.armhf | Arch.armv7:
                return "arm"
            case Arch.aarch64:
                return "arm64"
            case Arch.riscv64:
                return "riscv"
            case Arch.ppc64le | Arch.ppc64 | Arch.ppc:
                return "powerpc"
            case Arch.s390x:
                return "s390"
            case Arch.loongarch64 | Arch.loongarch32 | Arch.loongarchx32:
                return "loongarch"
            case _:
                return self.value

    def kernel_arch(self) -> str:
        """Value to use for ARCH= when building the Linux kernel."""
        match self:
            case Arch.x86:
                return "i386"
            case Arch.x86_64:
                return "x86_64"
            case _:
                return self.kernel_dir()

    def qemu_user(self) -> str:
        match self:
            case Arch.x86:
                return "i386"
            case Arch.armhf | Arch.armv7:
                return "arm"
            case _:
                return self.value

    def qemu_system(self) -> str:
        match self:
            case Arch.ppc64le:
                return "ppc64"
            case _:
                return self.qemu_user()

    def alpine_triple(self) -> str:
        """Get the cross compiler triple for this architecture on Alpine."""
        match self:
            case Arch.aarch64:
                return "aarch64-alpine-linux-musl"
            case Arch.armel:
                return "armv5-alpine-linux-musleabi"
            case Arch.armhf:
                return "armv6-alpine-linux-musleabihf"
            case Arch.armv7:
                return "armv7-alpine-linux-musleabihf"
            case Arch.loongarch32:
                return "loongarch32-alpine-linux-musl"
            case Arch.loongarchx32:
                return "loongarchx32-alpine-linux-musl"
            case Arch.loongarch64:
                return "loongarch64-alpine-linux-musl"
            case Arch.mips:
                return "mips-alpine-linux-musl"
            case Arch.mips64:
                return "mips64-alpine-linux-musl"
            case Arch.mipsel:
                return "mipsel-alpine-linux-musl"
            case Arch.mips64el:
                return "mips64el-alpine-linux-musl"
            case Arch.ppc:
                return "powerpc-alpine-linux-musl"
            case Arch.ppc64:
                return "powerpc64-alpine-linux-musl"
            case Arch.ppc64le:
                return "powerpc64le-alpine-linux-musl"
            case Arch.riscv32:
                return "riscv32-alpine-linux-musl"
            case Arch.riscv64:
                return "riscv64-alpine-linux-musl"
            case Arch.s390x:
                return "s390x-alpine-linux-musl"
            case Arch.x86:
                return "i586-alpine-linux-musl"
            case Arch.x86_64:
                return "x86_64-alpine-linux-musl"
            case _:
                raise ValueError(
                    f"Can not map Alpine architecture '{self}' to the right hostspec value"
                )

    def go(self) -> str:
        match self:
            case Arch.armhf | Arch.armv7:
                return "arm"
            case Arch.aarch64:
                return "arm64"
            case Arch.riscv64 | Arch.ppc64le:
                return str(self)
            case Arch.x86:
                return "386"
            case Arch.x86_64:
                return "amd64"
            case Arch.loongarch64:
                return "loong64"
            case _:
                raise ValueError(f"Can not map architecture '{self}' to Go arch")

    def cpu_emulation_required(self) -> bool:
        # Obvious case: host arch is target arch
        if self == Arch.native():
            return False

        # Currently, the only case where CPU emulation isn't required for non-host
        # architectures is where the CPU supports 32-bit execution
        if not cpu_is_32_bit_capable():
            return True

        # Other cases: host arch on the left, target archs on the right
        not_required = {
            Arch.x86_64: [Arch.x86],
            Arch.armv7: [Arch.armel, Arch.armhf],
            Arch.aarch64: [Arch.armv7],
            Arch.loongarch64: [Arch.loongarch32],
        }

        # Not all aarch64 CPUs that are 32-bit capable are configured for
        # execution of ARMv6 binaries
        if Arch.native() == Arch.aarch64 and cp15_barriers_supported():
            not_required[Arch.aarch64].append(Arch.armhf)

        return not (Arch.native() in not_required and self in not_required[Arch.native()])

    def linux32_required(self) -> bool:
        # Currently, the only case where CPU emulation isn't required for non-host
        # architectures is where the CPU supports 32-bit execution
        return self != Arch.native() and not self.cpu_emulation_required()

    # Magic to let us use an arch as a Path element
    def __truediv__(self, other: object) -> Path:
        if isinstance(other, (PosixPath, PurePosixPath)):
            # Convert the other path to a relative path
            # FIXME: we should avoid creating absolute paths that we actually want
            # to make relative to the chroot...
            # if other.is_absolute():
            #   logging.warning("FIXME: absolute path made relative to Arch??")
            other = other.relative_to("/") if other.is_absolute() else other
            return Path(str(self)).joinpath(other)
        if isinstance(other, str):
            # Let's us do Arch / "whatever.apk" and magically produce a path
            # maybe this is a pattern we should avoid, but it seems somewhat
            # sensible
            return Path(str(self)).joinpath(other.strip("/"))

        return NotImplemented

    def __rtruediv__(self, other: object) -> Path:
        if isinstance(other, (PosixPath, PurePosixPath)):
            # Important to produce a new Path object here, otherwise we
            # end up with one object getting shared around and modified
            # and lots of weird stuff happens.
            return Path(other) / str(self)
        # We don't support str / Arch since that is a weird pattern

        return NotImplemented


_cached_native_arch = Arch.from_machine_type(platform.machine())
