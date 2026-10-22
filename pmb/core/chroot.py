# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import enum
from collections.abc import Generator
from pathlib import Path, PosixPath, PurePosixPath

import pmb.config
from pmb.core.arch import Arch

from .context import get_context


class ChrootType(enum.Enum):
    ROOTFS = "rootfs"
    BUILDROOT = "buildroot"
    INSTALLER = "installer"
    NATIVE = "native"
    IMAGE = "image"

    def __str__(self) -> str:
        return self.name


class Chroot:
    __type: ChrootType
    __name: str

    def __init__(self, suffix_type: ChrootType, name: str | Arch | None = "") -> None:
        # We use the native chroot as the buildroot when building for the host arch
        if suffix_type == ChrootType.BUILDROOT and isinstance(name, Arch) and name.is_native():
            suffix_type = ChrootType.NATIVE
            name = ""

        self.__type = suffix_type
        self.__name = str(name or "")

        self.__validate()

    def __validate(self) -> None:
        """Ensures that this suffix follows the correct format."""
        if self.__type not in ChrootType._member_map_.values():
            raise ValueError(f"Invalid chroot type: '{self.__type}'")

        # A buildroot suffix must have a name matching one of alpines
        # architectures.
        if self.__type == ChrootType.BUILDROOT and self.arch not in Arch.supported():
            raise ValueError(f"Invalid buildroot suffix: '{self.__name}'")

        # A rootfs or installer suffix must have a name matching a device.
        if self.__type in {ChrootType.INSTALLER, ChrootType.ROOTFS}:
            # FIXME: pmb.helpers.devices.find_path() requires args parameter
            pass

        # A native suffix must not have a name.
        if self.__type == ChrootType.NATIVE and self.__name != "":
            raise ValueError(f"The native suffix can't have a name but got: '{self.__name}'")

        if self.__type == ChrootType.IMAGE and not Path(self.__name).exists():
            raise ValueError(f"Image file '{self.__name}' does not exist")

        # rootfs suffixes must have a valid device name
        if self.__type == ChrootType.ROOTFS and (len(self.__name) < 3 or "-" not in self.__name):
            raise ValueError(f"Invalid device name: '{self.__name}'")

    def __str__(self) -> str:
        if len(self.__name) > 0 and self.type != ChrootType.IMAGE:
            return f"{self.__type.value}_{self.__name}"
        else:
            return self.__type.value

    @property
    def dirname(self) -> str:
        return f"chroot_{self}"

    @property
    def path(self) -> Path:
        return Path(get_context().config.work, self.dirname)

    def exists(self) -> bool:
        return (self / "bin/sh").is_symlink()

    def is_mounted(self) -> bool:
        return self.exists() and pmb.helpers.mount.ismount(self.path / "etc/apk/keys")

    @property
    def arch(self) -> Arch:
        if self.type == ChrootType.NATIVE:
            return Arch.native()
        if self.type == ChrootType.BUILDROOT:
            return Arch.from_str(self.name)
        # FIXME: this is quite delicate as it will only be valid
        # for certain pmbootstrap commands... It was like this
        # before but it should be fixed.
        arch = pmb.parse.deviceinfo().arch
        # FIXME: We will remove the arch property from deviceinfo soon, so don't bother fixing this
        # type error. See https://gitlab.postmarketos.org/postmarketOS/pmaports/-/issues/4353
        if arch is not None:  # type: ignore[comparison-overlap]
            return arch

        raise ValueError(f"Invalid chroot suffix: {self} (wrong device chosen in 'init' step?)")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return str(self) == other or self.path == Path(other) or self.name == other

        if isinstance(other, PosixPath):
            return self.path == other

        if not isinstance(other, Chroot):
            return NotImplemented

        return self.type == other.type and self.name == other.name

    def __truediv__(self, other: object) -> Path:
        if isinstance(other, (PosixPath, PurePosixPath)):
            # Convert the other path to a relative path
            # FIXME: we should avoid creating absolute paths that we actually want
            # to make relative to the chroot...
            other = other.relative_to("/") if other.is_absolute() else other
            return self.path.joinpath(other)
        if isinstance(other, str):
            return self.path.joinpath(other.strip("/"))

        return NotImplemented

    def __rtruediv__(self, other: object) -> Path:
        if isinstance(other, (PosixPath, PurePosixPath)):
            # Important to produce a new Path object here, otherwise we
            # end up with one object getting shared around and modified
            # and lots of weird stuff happens.
            return Path(other) / self.path
        if isinstance(other, str):
            # This implicitly creates a new Path object
            return other / self.path

        return NotImplemented

    @property
    def type(self) -> ChrootType:
        return self.__type

    @property
    def name(self) -> str:
        return self.__name

    @staticmethod
    def native() -> Chroot:
        return Chroot(ChrootType.NATIVE)

    @staticmethod
    def buildroot(arch: Arch) -> Chroot:
        return Chroot(ChrootType.BUILDROOT, arch)

    @staticmethod
    def rootfs(device: str) -> Chroot:
        return Chroot(ChrootType.ROOTFS, device)

    @staticmethod
    def from_str(s: str) -> Chroot:
        """Generate a Suffix from a suffix string like "buildroot_aarch64"."""
        parts = s.split("_", 1)
        stype = parts[0]

        if len(parts) == 2:
            # Will error if stype isn't a valid ChrootType
            # The name will be validated by the Chroot constructor
            return Chroot(ChrootType(stype), parts[1])

        # "native" is the only valid suffix type, the constructor(s)
        # will validate that stype is "native"
        return Chroot(ChrootType(stype))

    @staticmethod
    def iter_patterns() -> Generator[str, None, None]:
        """Generate suffix patterns for all valid suffix types"""
        for stype in ChrootType:
            if stype == ChrootType.NATIVE:
                yield f"chroot_{stype.value}"
            else:
                yield f"chroot_{stype.value}_*"

    @staticmethod
    def glob() -> Generator[Path, None, None]:
        """Glob all initialized chroot directories"""
        for pattern in Chroot.iter_patterns():
            yield from Path(get_context().config.work).glob(pattern)
