# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from pathlib import Path
from typing import Any

import pytest

from pmb.core.arch import Arch


def test_valid_arches() -> None:
    # Silly test
    assert Arch.native().is_native()

    # Test constructor interface
    assert Arch.from_str("x86") == Arch.x86
    assert Arch.from_str("x86_64") == Arch.x86_64
    assert Arch.from_str("aarch64") == Arch.aarch64
    assert Arch.from_str("armhf") == Arch.armhf

    # Test from_machine_type
    assert Arch.from_machine_type("i686") == Arch.x86
    assert Arch.from_machine_type("x86_64") == Arch.x86_64
    assert Arch.from_machine_type("aarch64") == Arch.aarch64

    # Check supported architectures
    assert Arch.x86 in Arch.supported()
    assert Arch.x86_64 in Arch.supported()
    assert Arch.aarch64 in Arch.supported()
    assert Arch.armhf in Arch.supported()
    assert Arch.armv7 in Arch.supported()
    assert Arch.riscv64 in Arch.supported()
    assert Arch.ppc64le in Arch.supported()
    assert Arch.s390x in Arch.supported()
    assert Arch.loongarch64 in Arch.supported()

    # kernel directory
    assert Arch.x86.kernel_dir() == "x86"
    assert Arch.x86_64.kernel_dir() == "x86"
    assert Arch.aarch64.kernel_dir() == "arm64"  # The fun one
    assert Arch.armhf.kernel_dir() == "arm"
    assert Arch.armv7.kernel_dir() == "arm"
    assert Arch.ppc64le.kernel_dir() == "powerpc"
    assert Arch.loongarch64.kernel_dir() == "loongarch"
    # kernel ARCH=
    assert Arch.x86.kernel_arch() == "i386"
    assert Arch.x86_64.kernel_arch() == "x86_64"
    assert Arch.aarch64.kernel_arch() == "arm64"
    assert Arch.armhf.kernel_arch() == "arm"
    assert Arch.armv7.kernel_arch() == "arm"
    assert Arch.ppc64le.kernel_arch() == "powerpc"
    assert Arch.loongarch64.kernel_arch() == "loongarch"

    # qemu arch
    assert Arch.x86.qemu_system() == "i386"
    assert Arch.x86.qemu_user() == "i386"
    assert Arch.x86_64.qemu_system() == "x86_64"
    assert Arch.x86_64.qemu_user() == "x86_64"
    assert Arch.aarch64.qemu_system() == "aarch64"
    assert Arch.aarch64.qemu_user() == "aarch64"
    assert Arch.armhf.qemu_system() == "arm"
    assert Arch.armhf.qemu_user() == "arm"
    assert Arch.armv7.qemu_system() == "arm"
    assert Arch.armv7.qemu_user() == "arm"
    assert Arch.ppc64.qemu_system() == "ppc64"
    assert Arch.ppc64.qemu_user() == "ppc64"
    assert Arch.ppc64le.qemu_system() == "ppc64"
    assert Arch.ppc64le.qemu_user() == "ppc64le"
    assert Arch.loongarch64.qemu_system() == "loongarch64"
    assert Arch.loongarch64.qemu_user() == "loongarch64"

    # Go arch
    assert Arch.armhf.go() == "arm"
    assert Arch.armv7.go() == "arm"
    assert Arch.aarch64.go() == "arm64"
    assert Arch.riscv64.go() == "riscv64"
    assert Arch.ppc64le.go() == "ppc64le"
    assert Arch.x86_64.go() == "amd64"
    assert Arch.loongarch64.go() == "loong64"
    with pytest.raises(ValueError) as excinfo:
        Arch.mips64.go()
    assert "Can not map architecture 'mips64' to Go arch" in str(excinfo.value)

    # Check that Arch.cpu_emulation_required() works
    assert Arch.native() == Arch.x86_64 or Arch.x86_64.cpu_emulation_required()
    assert Arch.native() == Arch.aarch64 or Arch.aarch64.cpu_emulation_required()

    # Check that every arch has a target triple (except "noarch")
    for arch in Arch:
        if arch == Arch.noarch:
            continue
        assert arch.alpine_triple()

    # Arch-as-path magic
    assert Arch.aarch64 / Path("beep") == Path("aarch64/beep")
    assert os.fspath(Arch.aarch64 / "beep") == "aarch64/beep"
    assert isinstance(Arch.aarch64 / "beep", Path)
    assert (Arch.aarch64 / "beep").name == "beep"
    assert Path("boop") / Arch.aarch64 == Path("boop/aarch64")


def test_invalid_arches() -> None:
    excinfo: Any
    with pytest.raises(ValueError) as excinfo:
        Arch.from_str("invalid")
    assert "Invalid architecture: 'invalid'" in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        Arch.aarch64 / 5
    assert "unsupported operand type(s) for /: 'Arch' and 'int'" in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        "bap" / Arch.aarch64
    assert "unsupported operand type(s) for /: 'str' and 'Arch'" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        Arch.from_machine_type("invalid")
    assert "Unsupported machine type 'invalid'" in str(excinfo.value)


def test_arch_field_parsing() -> None:
    assert len(Arch.from_arch_field([])) == 0
    assert Arch.aarch64 in Arch.from_arch_field(["noarch"])
    assert Arch.aarch64 not in Arch.from_arch_field(["noarch", "!aarch64"])
    assert Arch.aarch64 in Arch.from_arch_field(["all"])
    assert Arch.aarch64 not in Arch.from_arch_field(["all", "!aarch64"])
    assert Arch.armv7 in Arch.from_arch_field(["armv7", "aarch64"])
    assert Arch.armel not in Arch.from_arch_field(["armv7", "aarch64"])
