# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.chroot.other
from pmb.core import Chroot, ChrootType


def _parse_flavor(device: str, autoinstall: bool = True) -> str:
    """
    Verify the flavor argument if specified, or return a default value.

    :param autoinstall: make sure that at least one kernel flavor is installed
    """
    # Install a kernel and get its "flavor", where flavor is a pmOS-specific
    # identifier that is typically in the form
    # "postmarketos-<manufacturer>-<device/chip>", e.g.
    # "postmarketos-qcom-sdm845"
    chroot = Chroot(ChrootType.ROOTFS, device)
    flavor = pmb.chroot.other.kernel_flavor_installed(chroot, autoinstall)

    if not flavor:
        raise RuntimeError(
            f"No kernel flavors installed in chroot '{chroot}'! Please let"
            " your device package depend on a package starting with 'linux-'."
        )
    return flavor
