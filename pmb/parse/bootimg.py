# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path
from typing import Literal, TextIO

import pmb.chroot
import pmb.chroot.apk
import pmb.helpers.run
from pmb.core import Chroot
from pmb.core.context import get_context
from pmb.helpers import logging
from pmb.types import Bootimg, PathString


def is_dtb(path: PathString) -> bool:
    if not os.path.isfile(path):
        return False
    with open(path, "rb") as f:
        # Check FDT magic identifier (0xd00dfeed)
        return f.read(4) == b"\xd0\x0d\xfe\xed"


def get_mtk_label(path: PathString) -> str | None:
    """
    Read the label from the MediaTek header of the kernel or ramdisk inside
    an extracted boot.img.

    :param path: to either the kernel or ramdisk extracted from boot.img
    :returns: * None: file does not exist or does not have MediaTek header

    * Label string (e.g. "ROOTFS", "KERNEL")
    """
    if not os.path.exists(path):
        return None

    with open(path, "rb") as f:
        # Check Mediatek header (0x88168858)
        if f.read(4) != b"\x88\x16\x88X":
            return None
        f.seek(8)
        label = f.read(32).decode("utf-8").rstrip("\0")

        if label == "RECOVERY":
            logging.warning(
                "WARNING: This boot.img has MediaTek headers. Since you passed a"
                " recovery image instead of a regular boot.img, we can't tell what"
                " the ramdisk signature label is supposed to be, so we assume that"
                " it's the most common value, ROOTFS. There is a chance that this"
                " is wrong and it may not boot; in that case, run bootimg_analyze"
                " again with a regular boot.img. If this *is* a regular boot.img,"
                " replace the value of deviceinfo_bootimg_mtk_label_ramdisk with"
                " 'RECOVERY'."
            )
            return "ROOTFS"
        else:
            return label


def get_qcdt_type(path: PathString) -> Literal["qcom", "sprd", "exynos"] | None:
    """
    Get the dt.img type by reading the first four bytes of the file.

    :param path: to the qcdt image extracted from boot.img
    :returns: * None: dt.img is of unknown type
    """
    if not os.path.exists(path):
        return None

    with open(path, "rb") as f:
        fourcc = f.read(4)

        match fourcc:
            case b"QCDT":
                return "qcom"
            case b"SPRD":
                return "sprd"
            case b"DTBH":
                return "exynos"
            case _:
                return None


def get_qcdt_exynos_platform_subtype(path: PathString) -> tuple[str, str] | tuple[None, None]:
    """
    Get the exynos dt.img platform and subtype by reading the first
    four bytes of the file.

    :param path: to the qcdt image extracted from boot.img
    :returns: ( Type tuple with platform and subtype, like ("0x50a6", "0x217584da")
    """
    if not os.path.exists(path):
        return (None, None)

    with open(path, "rb") as f:
        header = f.read(24)

    platform = hex(int.from_bytes(header[16:20], "little"))
    subtype = hex(int.from_bytes(header[20:24], "little"))

    return (platform, subtype)


def bootimg(path: Path) -> Bootimg:
    if not path.exists():
        raise RuntimeError(f"Could not find file '{path}'")

    logging.info(
        "NOTE: You will be prompted for your sudo/doas/run0 password, so"
        " we can set up a chroot to extract and analyze your"
        " boot.img file"
    )
    pmb.chroot.init(Chroot.native())
    pmb.chroot.apk.install(["file", "unpackbootimg"], Chroot.native())

    temp_path = Path("/tmp/bootimg_parser")
    pmb.chroot.user(["mkdir", "-p", temp_path])
    bootimg_path = Chroot.native() / temp_path / "boot.img"

    # Copy the boot.img into the chroot temporary folder
    # and make it world readable
    pmb.helpers.run.root(["cp", path, bootimg_path])
    pmb.helpers.run.root(["chmod", "a+r", bootimg_path])

    file_output = pmb.chroot.user(
        ["file", "-b", "boot.img"], working_dir=temp_path, output_return=True
    ).rstrip()
    if "android bootimg" not in file_output.lower():
        if get_context().force:
            logging.warning(
                "WARNING: boot.img file seems to be invalid, but proceeding anyway (-f specified)"
            )
        else:
            logging.info(
                "NOTE: If you are sure that your file is a valid"
                " boot.img file, you could force the analysis"
                f" with: 'pmbootstrap bootimg_analyze {path} -f'"
            )
            if (
                "linux kernel" in file_output.lower()
                or "ARM OpenFirmware FORTH dictionary" in file_output
            ):
                raise RuntimeError(
                    "File is a Kernel image, you might need the"
                    " 'heimdall-isorec' flash method. See also:"
                    " <https://wiki.postmarketos.org/wiki/"
                    "Deviceinfo_flash_methods>"
                )
            else:
                raise RuntimeError("File is not an Android boot.img. (" + file_output + ")")

    # Extract all the files
    pmb.chroot.user(["unpackbootimg", "-i", "boot.img"], working_dir=temp_path)

    output = {}
    header_version = 0
    # Get base, offsets, pagesize, cmdline and qcdt info
    # This file does not exist for example for qcdt images
    bootimg_header_version = Path(f"{bootimg_path}-header_version")
    if bootimg_header_version.exists():
        header_version = int(bootimg_header_version.read_text().replace("\n", ""))

    if header_version >= 3:
        output["pagesize"] = "4096"
    else:
        addresses = {
            "base": f"{bootimg_path}-base",
            "kernel_offset": f"{bootimg_path}-kernel_offset",
            "ramdisk_offset": f"{bootimg_path}-ramdisk_offset",
            "second_offset": f"{bootimg_path}-second_offset",
            "tags_offset": f"{bootimg_path}-tags_offset",
        }
        if header_version == 2:
            addresses["dtb_offset"] = f"{bootimg_path}-dtb_offset"
        for key, file in addresses.items():
            with open(file) as f:
                output[key] = f"0x{int(trim_input(f), 16):08x}"

        with open(f"{bootimg_path}-pagesize") as f:
            output["pagesize"] = trim_input(f)

    output["bootimg_qcdt"] = (
        "true"
        if os.path.isfile(f"{bootimg_path}-dt") and os.path.getsize(f"{bootimg_path}-dt") > 0
        else "false"
    )
    output.update(
        {
            key: value
            for key, value in {
                "mtk_label_kernel": get_mtk_label(f"{bootimg_path}-kernel"),
                "mtk_label_ramdisk": get_mtk_label(f"{bootimg_path}-ramdisk"),
                "bootimg_qcdt_type": get_qcdt_type(f"{bootimg_path}-dt"),
            }.items()
            if value is not None
        }
    )
    if "bootimg_qcdt_type" in output and output["bootimg_qcdt_type"] == "exynos":
        platform, subtype = get_qcdt_exynos_platform_subtype(f"{bootimg_path}-dt")
        # Omit if platform is default value 0x50a6
        if platform and platform != "0x50a6":
            output.update({"bootimg_qcdt_exynos_platform": platform})
        # Omit if subtype is default value 0x217584da
        if subtype and subtype != "0x217584da":
            output.update({"bootimg_qcdt_exynos_subtype": subtype})

    output["dtb_second"] = "true" if is_dtb(f"{bootimg_path}-second") else ""

    with open(f"{bootimg_path}-cmdline") as f:
        output["cmdline"] = trim_input(f)

    # Cleanup
    pmb.chroot.user(["rm", "-r", temp_path])

    return Bootimg(
        cmdline=output["cmdline"],
        bootimg_qcdt=output["bootimg_qcdt"],
        bootimg_qcdt_type=output.get("bootimg_qcdt_type"),
        bootimg_qcdt_exynos_platform=output.get("bootimg_qcdt_exynos_platform", ""),
        bootimg_qcdt_exynos_subtype=output.get("bootimg_qcdt_exynos_subtype", ""),
        dtb_offset=output.get("dtb_offset"),
        dtb_second=output["dtb_second"],
        base=output.get("base", ""),
        kernel_offset=output.get("kernel_offset", ""),
        ramdisk_offset=output.get("ramdisk_offset", ""),
        second_offset=output.get("second_offset", ""),
        tags_offset=output.get("tags_offset", ""),
        pagesize=output["pagesize"],
        header_version=header_version,
        mtk_label_kernel=output.get("mtk_label_kernel", ""),
        mtk_label_ramdisk=output.get("mtk_label_ramdisk", ""),
    )


def trim_input(f: TextIO) -> str:
    return f.read().replace("\n", "")
