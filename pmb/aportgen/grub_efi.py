# Copyright 2023 Nick Reitemeyer, Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.aportgen.core
import pmb.build
import pmb.helpers.repo
import pmb.parse.apkindex
from pmb.core import Chroot
from pmb.core.arch import Arch


def generate(pkgname: str) -> None:
    arch = Arch.x86
    if pkgname != "grub-efi-x86":
        raise RuntimeError("only grub-efi-x86 is available")
    # Update or create APKINDEX for relevant arch so we know it exists and is recent.
    pmb.helpers.repo.update(arch)

    package_data = pmb.parse.apkindex.package("grub", arch=arch)
    version = package_data.version
    pkgver = version.split("-r")[0]
    pkgrel = version.split("-r")[1]

    tempdir = pmb.aportgen.core.prepare_tempdir()

    # Write the APKBUILD
    channel_cfg = pmb.config.pmaports.read_config_channel()
    mirrordir = channel_cfg["mirrordir_alpine"]
    apkbuild_path = Chroot.native() / tempdir / "APKBUILD"
    apk_name = f'"$srcdir/grub-efi-$pkgver-r$pkgrel-$_arch-{mirrordir}.apk"'
    with open(apkbuild_path, "w", encoding="utf-8") as handle:
        apkbuild = f"""\
            # Automatically generated aport, do not edit!
            # Generator: pmbootstrap aportgen {pkgname}

            maintainer=""
            pkgname={pkgname}
            pkgver={pkgver}
            pkgrel={pkgrel}

            _arch="{arch}"
            _mirror="{pmb.config.aportgen_mirror_alpine}"

            pkgdesc="GRUB $_arch EFI files for every architecture"
            url="https://www.gnu.org/software/grub/"
            license="GPL-3.0-or-later"
            arch="{Arch.native()}"
            source="grub-efi-$pkgver-r$pkgrel-$_arch-{mirrordir}.apk::$_mirror/{mirrordir}/main/$_arch/grub-efi-$pkgver-r$pkgrel.apk"

            package() {{
                mkdir -p "$pkgdir"
                cd "$pkgdir"
                tar -xf {apk_name}
                rm .PKGINFO .SIGN.*
            }}
        """
        handle.writelines(line[12:].replace(" " * 4, "\t") + "\n" for line in apkbuild.split("\n"))

    pmb.aportgen.core.generate_checksums(tempdir, apkbuild_path)
