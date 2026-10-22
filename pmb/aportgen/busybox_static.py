# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.aportgen.core
import pmb.build
import pmb.helpers.repo
import pmb.parse.apkindex
from pmb.core import Chroot
from pmb.core.arch import Arch


def generate(pkgname: str) -> None:
    arch = Arch.from_str(pkgname.split("-")[2])

    # Update or create APKINDEX for relevant arch so we know it exists and is recent.
    pmb.helpers.repo.update(arch)
    # Parse version from APKINDEX
    package_data = pmb.parse.apkindex.package("busybox", arch=arch)

    version = package_data.version
    pkgver = version.split("-r")[0]
    pkgrel = version.split("-r")[1]

    tempdir = pmb.aportgen.core.prepare_tempdir()

    # Write the APKBUILD
    channel_cfg = pmb.config.pmaports.read_config_channel()
    mirrordir = channel_cfg["mirrordir_alpine"]
    apkbuild_path = Chroot.native() / tempdir / "APKBUILD"
    apk_name = f"busybox-static-$pkgver-r$pkgrel-$_arch-{mirrordir}.apk"
    with open(apkbuild_path, "w", encoding="utf-8") as handle:
        apkbuild = f"""\
            # Automatically generated aport, do not edit!
            # Generator: pmbootstrap aportgen {pkgname}

            # Stub for apkbuild-lint
            if [ -z "$(type -t arch_to_hostspec)" ]; then
                arch_to_hostspec() {{ :; }}
            fi

            maintainer=""
            pkgname={pkgname}
            pkgver={pkgver}
            pkgrel={pkgrel}

            _arch="{arch}"
            _mirror="{pmb.config.aportgen_mirror_alpine}"

            url="http://busybox.net"
            license="GPL-2.0-only"
            arch="{pmb.aportgen.get_cross_package_arches(pkgname)}"
            options="!check !strip"
            pkgdesc="Statically linked Busybox for $_arch"
            _target="$(arch_to_hostspec $_arch)"

            source="
                busybox-static-$pkgver-r$pkgrel-$_arch-{mirrordir}.apk::$_mirror/{mirrordir}/main/$_arch/busybox-static-$pkgver-r$pkgrel.apk
            "

            package() {{
                mkdir -p "$pkgdir/usr/$_target"
                cd "$pkgdir/usr/$_target"
                tar -xf $srcdir/{apk_name}
                rm .PKGINFO .SIGN.*
            }}
        """
        handle.writelines(line[12:].replace(" " * 4, "\t") + "\n" for line in apkbuild.split("\n"))

    pmb.aportgen.core.generate_checksums(tempdir, apkbuild_path)
