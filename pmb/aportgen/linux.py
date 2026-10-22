# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.helpers.run
import pmb.parse.apkindex
from pmb.aportgen.device import ask_for_architecture
from pmb.core.context import get_context
from pmb.helpers.exceptions import NonBugError
from pmb.parse.deviceinfo import Deviceinfo


def generate_apkbuild(
    pkgname: str,
    deviceinfo: Deviceinfo | None,
    patches: list[str],
    device_category: pmb.helpers.devices.DeviceCategory,
) -> None:
    arch = deviceinfo.arch if deviceinfo else ask_for_architecture()
    carch = arch.kernel_arch()

    makedepends = [
        "bison",
        "elfutils-dev",
        "findutils",
        "flex",
        "linux-headers",
        "openssl-dev",
        "pahole",
        "perl",
        "python3",
    ]

    patches_str = ("\n" + " " * 12).join(patches)
    config = "config-${pkgname#linux-}.$arch"
    # TODO: remove once this line is in the minimum pmb version in pmaports
    flavor = "${pkgname#linux-}"

    # Downstream kernel
    if device_category == pmb.helpers.devices.DeviceCategory.DOWNSTREAM:
        reference_url = "https://nura.eco/vendorkernel"

        makedepends += [
            "bash",
            "bc",
            "devicepkg-dev",
        ]

        source = f"""source="
            $pkgname-$_commit.tar.gz::https://github.com/(CHANGEME_Organization!)/(CHANGEME_Repository!)/archive/$_commit.tar.gz
            {config}
            {patches_str}
            \""""

        outdir = '_outdir="out"\n'

        prepare = """
            default_prepare
            . downstreamkernel_prepare"""

        build = """
            unset LDFLAGS
            make O="$_outdir" ARCH="$_carch" CC="${CC:-gcc}" \\
                KBUILD_BUILD_VERSION="$((pkgrel + 1 ))"-postmarketOS"""

        package = """
            downstreamkernel_package "$builddir" "$pkgdir" "$_carch\" \\
                "${pkgname#linux-}" "$_outdir\""""

        if deviceinfo:
            has_dtb = deviceinfo.header_version and deviceinfo.header_version >= 2
        else:
            has_dtb = pmb.helpers.cli.confirm(
                "Does the device use DTBs?", default=True, no_assumptions=True
            )

        if has_dtb:
            package += """
            make dtbs_install O="$_outdir" ARCH="$_carch" \\
                INSTALL_DTBS_PATH="$pkgdir\"/boot/dtbs"""

        if deviceinfo:
            has_qcdt = deviceinfo.bootimg_qcdt == "true"
        else:
            has_qcdt = pmb.helpers.cli.confirm(
                "Does the device use QCDT (see <https://wiki.nura.eco/wiki/QCDT>)?",
                default=False,
                no_assumptions=True,
            )

        if has_qcdt:
            build += """\n
            # Master DTB (deviceinfo_bootimg_qcdt)"""
            vendors = ["spreadtrum", "exynos", "other"]
            soc_vendor = pmb.helpers.cli.ask("SoC vendor", vendors, vendors[-1], complete=vendors)
            if soc_vendor == "spreadtrum":
                makedepends.append("dtbtool-sprd")
                build += """
            dtbTool-sprd -p "$_outdir"/scripts/dtc/ \\
                -o "$_outdir"/arch/"$_carch"/boot/dt.img \\
                "$_outdir/arch/$_carch/boot/dts/\""""
            elif soc_vendor == "exynos":
                codename = "-".join(pkgname.split("-")[2:])
                makedepends.append("dtbtool-exynos")
                build += """
            dtbTool-exynos -o "$_outdir"/arch/"$_carch"/boot/dt.img \\
                $(find "$_outdir"/arch/"$_carch"/boot/dts/"""
                build += f" -name *{codename}*.dtb)"
            else:
                makedepends.append("dtbtool")
                build += """
            dtbTool -o "$_outdir"/arch/"$_carch"/boot/dt.img \\
                "$_outdir"/arch/"$_carch"/boot/"""
            package += """
            install -Dm644 "$_outdir"/arch/"$_carch"/boot/dt.img \\
                "$pkgdir"/boot/dt.img"""

    # Mainline kernel
    else:
        reference_url = None

        # Add mainline dependencies
        makedepends += ["clang", "lld", "llvm", "postmarketos-installkernel", "zstd"]

        source = f"""source="
            $pkgname-$_commit.tar.gz::https://github.com/(CHANGEME_Organization!)/(CHANGEME_Repository!)/archive/$_commit.tar.gz
            {config}
            \""""

        outdir = ""

        prepare = f"""
            default_prepare
            cp "$srcdir"/{config} .config"""

        build = """
            unset LDFLAGS
            make ARCH="$_carch" LLVM=1 \\
                KBUILD_BUILD_VERSION="$((pkgrel + 1 ))"-postmarketOS"""

        package = """
            mkdir -p "$pkgdir"/boot
            make zinstall modules_install dtbs_install \\
                ARCH="$_carch" \\
                LLVM=1 \\
                INSTALL_MOD_STRIP=1 \\
                INSTALL_PATH="$pkgdir"/boot \\
                INSTALL_MOD_PATH="$pkgdir"/usr \\
                INSTALL_DTBS_PATH="$pkgdir"/boot/dtbs

            rm -f "$pkgdir"/usr/lib/modules/*/build "$pkgdir"/usr/lib/modules/*/source

            install -Dm644 "$builddir"/include/config/kernel.release \\
                -t "$pkgdir"/usr/share/kernel/"${pkgname#linux-}"/"""

    makedepends.sort()
    makedepends_fmt = ("\n" + " " * 12).join(makedepends)
    reference_str = " " * 8 + f"# Reference: <{reference_url}>\n" if reference_url else ""
    content = f"""{reference_str}\
        # Kernel config based on: arch/{carch}/configs/(CHANGEME!)
        maintainer=""
        pkgname={pkgname}
        pkgver=3.x.x
        pkgrel=0
        _commit=ffffffffffffffffffffffffffffffffffffffff
        pkgdesc="{deviceinfo.name if deviceinfo else "(CHANGEME!)"} kernel fork"
        arch="{arch}"
        url="https://kernel.org"
        license="GPL-2.0-only"
        makedepends="
            {makedepends_fmt}
            "
        {source}
        builddir="$srcdir/(CHANGEME_Repository!)-$_commit"
        options="
            !check
            !strip
            !tracedeps
            pmb:cross-native
            "
        {outdir}
        _carch="{carch}"

        # Used internally by pmbootstrap. Don't touch.
        # TODO: Remove once minimum default pmbootstrap version supports
        # kernel packages without '_flavor' and '_config'.
        _config="{config}"
        _flavor="{flavor}"

        prepare() {{{prepare}
        }}

        build() {{{build}
        }}

        package() {{{package}
        }}

        sha512sums="(run 'pmbootstrap checksum {pkgname}' to fill)"
        """

    # Write the file
    with (get_context().config.work / "aportgen/APKBUILD").open("w", encoding="utf-8") as hndl:
        for line in content.rstrip().split("\n"):
            hndl.write(line[8:].replace(" " * 4, "\t") + "\n")


def generate(pkgname: str, device_category: pmb.helpers.devices.DeviceCategory) -> None:
    device = "-".join(pkgname.split("-")[1:])
    try:
        deviceinfo = pmb.parse.deviceinfo(device)
    except NonBugError:  # device not found
        deviceinfo = None
    work = get_context().config.work

    pmb.helpers.run.user(["mkdir", "-p", work / "aportgen"])

    # Symlink commonly used patches
    if device_category == pmb.helpers.devices.DeviceCategory.DOWNSTREAM:
        patches = [
            "gcc7-give-up-on-ilog2-const-optimizations.patch",
            "gcc8-fix-put-user.patch",
            "gcc10-extern_YYLOC_global_declaration.patch",
            "kernel-use-the-gnu89-standard-explicitly.patch",
        ]
        for patch in patches:
            pmb.helpers.run.user(
                ["ln", "-s", "../../.shared-patches/linux/" + patch, (work / "aportgen" / patch)]
            )
    else:
        patches = []

    generate_apkbuild(pkgname, deviceinfo, patches, device_category)
