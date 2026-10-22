# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.config
import pmb.helpers.pmaports
from pmb.core.apk_package import Apkbuild
from pmb.core.arch import Arch
from pmb.core.context import get_context
from pmb.meta import Cache
from pmb.types import CrossCompile


@Cache("package")
def arch(package: str | Apkbuild) -> Arch:
    """
    Find a good default in case the user did not specify for which architecture
    a package should be built.

    :param package: The name of the package or parsed APKBUILD

    :returns: Arch object. Preferred order, depending
              on what is supported by the APKBUILD:
              * native arch
              * device arch (this will be preferred instead if build_default_device_arch is true)
              * first arch in the APKBUILD
    """
    pkgname = package["pkgname"] if isinstance(package, dict) else package
    aport = pmb.helpers.pmaports.find(pkgname)

    apkbuild = pmb.parse.apkbuild(aport) if isinstance(package, str) else package
    arches = Arch.from_arch_field(apkbuild["arch"])
    deviceinfo = pmb.parse.deviceinfo()

    if get_context().config.build_default_device_arch:
        preferred_arch = deviceinfo.arch
        preferred_arch_2nd = Arch.native()
    else:
        preferred_arch = Arch.native()
        preferred_arch_2nd = deviceinfo.arch

    if preferred_arch in arches:
        return preferred_arch

    if preferred_arch_2nd in arches:
        return preferred_arch_2nd

    try:
        arch_str = apkbuild["arch"][0]
        return Arch.from_str(arch_str) if arch_str else Arch.native()
    except IndexError:
        return Arch.native()


def crosscompile(apkbuild: Apkbuild, arch: Arch) -> CrossCompile:
    """Decide the type of compilation necessary to build a given APKBUILD."""
    if not get_context().cross:
        return CrossCompile.QEMU_ONLY
    if not arch.cpu_emulation_required():
        return CrossCompile.UNNECESSARY
    if "pmb:cross-native" in apkbuild["options"]:
        return CrossCompile.CROSS_NATIVE
    # In case we end up being requested to cross-compile a "noarch" package,
    # default to cross-native2 if the package has "noarch" since that implies
    # it won't run a compiler. This can happen if e.g. the --arch argument is
    # set to a foreign architecture when calling the build subcommand or as
    # part of the install subcommand when building an image for a foreign
    # architecture.
    if (
        arch.is_native()
        or "pmb:cross-native2" in apkbuild["options"]
        or apkbuild["arch"] == ["noarch"]
    ):
        return CrossCompile.CROSS_NATIVE2
    if "!pmb:crossdirect" in apkbuild["options"]:
        return CrossCompile.QEMU_ONLY
    return CrossCompile.CROSSDIRECT
