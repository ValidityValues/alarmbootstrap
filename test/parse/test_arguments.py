# Copyright 2025 Pablo Correa Gomez
# SPDX-License-Identifier: GPL-3.0-or-later

from pmb.parse import get_parser


def test_chroot_simple() -> None:
    parser = get_parser()
    args = parser.parse_args("chroot ls".split())
    assert args.action == "chroot"
    assert args.command == ["ls"]


def test_chroot_args() -> None:
    parser = get_parser()
    args = parser.parse_args("chroot --rootfs -- ls -l".split())
    assert args.action == "chroot"
    assert args.rootfs is True
    assert args.command == ["ls", "-l"]
