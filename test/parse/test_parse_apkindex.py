# Copyright 2024 Casey Connolly
# SPDX-License-Identifier: GPL-3.0-or-later
# mypy: disable-error-code="comparison-overlap"

from pathlib import Path
from typing import NoReturn

import pytest
from _pytest.monkeypatch import MonkeyPatch

from pmb.core.apk_package import ApkPackage
from pmb.core.apkindex import Apkindex
from pmb.core.arch import Arch
from pmb.parse.apkindex import (
    clear_cache as clear_apkindex_cache,
    package as package_apkindex,
    parse as parse_apkindex,
)


def test_apkindex_parse(valid_apkindex_file: Apkindex) -> None:
    tmpfile = valid_apkindex_file
    blocks = parse_apkindex(tmpfile, True)
    for k, v in blocks.items():
        print(f"{k}: {v}")

    # Even though there's only 14 entries, there are some virtual packages
    assert len(blocks) == 18

    # Check that the postmarketos-ramdisk virtual package is handled correctly
    # and that it's one provider (postmarketos-initramfs) is declared
    assert "postmarketos-ramdisk" in blocks
    assert "postmarketos-initramfs" in blocks["postmarketos-ramdisk"]
    assert (
        blocks["postmarketos-ramdisk"]["postmarketos-initramfs"]
        == blocks["postmarketos-initramfs"]["postmarketos-initramfs"]
    )

    initramfs = blocks["postmarketos-initramfs"]["postmarketos-initramfs"]
    assert initramfs.pkgname == "postmarketos-initramfs"
    assert initramfs.provides == ["postmarketos-ramdisk"]
    assert initramfs.provider_priority == 10
    assert initramfs.depends == [
        "blkid",
        "btrfs-progs",
        "buffyboard",
        "busybox-extras",
        "bzip2",
        "cryptsetup",
        "device-mapper",
        "devicepkg-utils",
        "dosfstools",
        "e2fsprogs",
        "e2fsprogs-extra",
        "f2fs-tools",
        "font-terminus",
        "iskey",
        "kmod",
        "libinput-libs",
        "lz4",
        "multipath-tools",
        "parted",
        "postmarketos-fde-unlocker",
        "postmarketos-mkinitfs",
        "udev",
        "unudhcpd",
        "util-linux-misc",
        "xz",
    ]

    tinydm = blocks["postmarketos-base-ui-tinydm"]["postmarketos-base-ui-tinydm"]
    # Without the version!
    assert tinydm.provides == ["postmarketos-base-tinydm"]
    assert tinydm.version == "29-r1"
    assert tinydm.arch == Arch.aarch64

    wayland = blocks["postmarketos-base-ui-wayland"]["postmarketos-base-ui-wayland"]
    # Doesn't provide an explicit version
    assert wayland.provides == []
    assert wayland.origin == "postmarketos-base-ui"

    networkmanager = blocks["postmarketos-base-ui-networkmanager"][
        "postmarketos-base-ui-networkmanager"
    ]
    assert networkmanager.provider_priority is None


def test_apkindex_parse_trailing_newline(tmp_path: Path) -> None:
    tmpfile = Apkindex(tmp_path / "APKINDEX.4")
    # A snippet of the above example but with additional
    # trailing newlines
    tmpfile.write_text("""
C:Q1yB3CVUFMOjnLOOEAUIUUpJJV8g0=
P:postmarketos-base-ui-x11
V:29-r1
A:aarch64
S:1587
I:22
T:Meta package for minimal postmarketOS UI base
U:https://postmarketos.org
L:GPL-3.0-or-later
m:Clayton Craft <clayton@craftyguy.net>
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:libinput xf86-input-libinput xf86-video-fbdev
p:postmarketos-base-x11=29-r1
i:postmarketos-base-ui=29-r1 xorg-server


""")

    # We expect parsing to succeed when the timestamp is missing
    parse_apkindex(tmpfile, True)


def test_apkindex_parse_cache_hit(valid_apkindex_file: Apkindex, monkeypatch: MonkeyPatch) -> None:
    # First parse normally, filling the cache
    parse_apkindex(valid_apkindex_file)

    # Mock that always asserts when called
    def mock_assert(cls: type[NoReturn], lines: list[str]) -> ApkPackage:
        assert False

    # ApkPackage.from_apkindex_block() is only called on cache miss
    monkeypatch.setattr(ApkPackage, "from_apkindex_block", classmethod(mock_assert))

    # Now we expect the cache to be hit and thus the mock won't be called, so no assertion error
    parse_apkindex(valid_apkindex_file)

    # Now we clear the cache, the mock should be called and we'll assert
    clear_apkindex_cache(valid_apkindex_file)

    with pytest.raises(AssertionError):
        parse_apkindex(valid_apkindex_file)


def test_apkindex_package(valid_apkindex_file: Apkindex) -> None:
    index_block = package_apkindex(
        "postmarketos-base-ui-networkmanager", arch=Arch.aarch64, indexes=[valid_apkindex_file]
    )
    assert index_block is not None
    assert index_block.pkgname == "postmarketos-base-ui-networkmanager"

    index_block = package_apkindex(
        "postmarketos-base-ui-wifi", arch=Arch.aarch64, indexes=[valid_apkindex_file]
    )
    assert index_block is not None
    assert index_block.pkgname == "postmarketos-base-ui-wifi-wpa_supplicant"


def test_apkindex_package_provider_priority(tmp_path: Path) -> None:
    tmpfile = Apkindex(tmp_path / "APKINDEX.5")
    # A snippet of the above example but with a missing timestamp
    # and origin fields
    tmpfile.write_text("""
C:Q1yB3CVUFMOjnLOOEAUIUUpJJV8g0=
P:postmarketos-base-short
V:20-r0
A:aarch64
S:1587
I:22
T:openrc config for postmarketOS
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:!systemd alpine-conf busybox-mdev-openrc busybox-openrc openrc
p:postmarketos-base-init
k:10

C:Q1yB3CVUFMOjnLOOEAUIUUpJJV8g0=
P:postmarketos-base-loooooooooong
V:22-r0
A:aarch64
S:1587
I:22
T:systemd base config for postmarketOS
U:https://postmarketos.org
L:GPL-3.0-or-later
o:postmarketos-base-systemd
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
D:kbd kmod less login-utils systemd systemd-services systemd-timesyncd tzdata
p:postmarketos-base-init
k:100
""")

    index_block = package_apkindex("postmarketos-base-init", arch=Arch.aarch64, indexes=[tmpfile])
    assert index_block is not None
    assert index_block.pkgname == "postmarketos-base-loooooooooong"
    assert index_block.origin == "postmarketos-base-systemd"
    assert index_block.provides == ["postmarketos-base-init"]


def test_apkindex_package_provider_shortest(tmp_path: Path) -> None:
    tmpfile = Apkindex(tmp_path / "APKINDEX.6")
    # A snippet of the above example but with a missing timestamp
    # and origin fields
    tmpfile.write_text("""
C:Q1yB3CVUFMOjnLOOEAUIUUpJJV8g0=
P:mesa-egl
V:20-r0
A:aarch64
S:1587
I:22
T:mesa package
U:https://postmarketos.org
L:GPL-3.0-or-later
o:mesa
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
p:so:libGL.so.1=20-r0

C:Q1yB3CVUFMOjnLOOEAUIUUpJJV8g0=
P:mesa-purism-gc7000-egl
V:22-r0
A:aarch64
S:1587
I:22
T:mesa fork for Purism
U:https://postmarketos.org
L:GPL-3.0-or-later
o:mesa-purism-gc7000
m:Clayton Craft <clayton@craftyguy.net>
t:1729538699
c:901cb9520450a1e88ded95ac774e83f6b2cfbba3-dirty
p:so:libGL.so.1=22-r0
""")

    index_block = package_apkindex("so:libGL.so.1", arch=Arch.aarch64, indexes=[tmpfile])
    assert index_block is not None
    assert index_block.pkgname == "mesa-egl"
    assert index_block.origin == "mesa"
