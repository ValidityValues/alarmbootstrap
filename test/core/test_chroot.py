# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from pmb.core.arch import Arch
from pmb.core.chroot import Chroot, ChrootType
from pmb.core.context import get_context


def test_valid_chroots(pmb_args: None, mock_devices_find_path: None) -> None:
    """Test that Chroot objects work as expected"""
    work = get_context().config.work

    chroot = Chroot.native()
    assert chroot.type == ChrootType.NATIVE
    assert chroot.name == ""
    assert chroot.arch in Arch.supported()
    assert not chroot.exists()  # Shouldn't be created
    assert chroot.path == work / "chroot_native"
    assert str(chroot) == "native"

    # Don't create an aarch64 buildroot on aarch64
    if chroot.arch != Arch.aarch64:
        chroot = Chroot.buildroot(Arch.aarch64)
        assert chroot.name == "aarch64"
        assert chroot.arch == Arch.aarch64
        assert chroot.path == work / "chroot_buildroot_aarch64"
        assert str(chroot) == "buildroot_aarch64"
    else:
        chroot = Chroot.buildroot(Arch.x86_64)
        assert chroot.name == "x86_64"
        assert chroot.arch == Arch.x86_64
        assert chroot.path == work / "chroot_buildroot_x86_64"
        assert str(chroot) == "buildroot_x86_64"
    assert chroot.type == ChrootType.BUILDROOT
    assert not chroot.exists()  # Shouldn't be created

    # FIXME: implicily assumes that we're mocking the qemu-amd64 deviceinfo
    chroot = Chroot(ChrootType.ROOTFS, "qemu-amd64")
    assert chroot.type == ChrootType.ROOTFS
    assert chroot.name == "qemu-amd64"
    assert chroot.arch == Arch.x86_64
    assert not chroot.exists()  # Shouldn't be created
    assert chroot.path == work / "chroot_rootfs_qemu-amd64"
    assert str(chroot) == "rootfs_qemu-amd64"


# mypy: ignore-errors
def test_invalid_chroots(pmb_args: None) -> None:
    """Test that we can't create invalid chroots."""
    with pytest.raises(ValueError) as excinfo:
        Chroot(ChrootType.BUILDROOT, "BAD_ARCH")
    assert (
        str(excinfo.value)
        == "Invalid architecture: 'BAD_ARCH', expected something like: aarch64, armhf, armv7, loongarch64, ppc64le, riscv64, s390x, x86, x86_64"
    )

    with pytest.raises(ValueError) as excinfo:
        Chroot(ChrootType.NATIVE, "aarch64")
    assert str(excinfo.value) == "The native suffix can't have a name but got: 'aarch64'"

    with pytest.raises(ValueError) as excinfo:
        Chroot("beep boop")
    assert str(excinfo.value) == "Invalid chroot type: 'beep boop'"

    with pytest.raises(ValueError) as excinfo:
        Chroot(5)
    assert str(excinfo.value) == "Invalid chroot type: '5'"


@pytest.mark.xfail
def test_untested_chroots() -> None:
    # IMAGE type is untested, name should be a valid path in this case
    tested_chroot_types = [
        ChrootType.ROOTFS,
        ChrootType.BUILDROOT,
        ChrootType.NATIVE,
        ChrootType.INSTALLER,
    ]
    for ct in ChrootType:
        if ct not in tested_chroot_types:
            raise ValueError(f"ChrootType {ct} is untested!")
