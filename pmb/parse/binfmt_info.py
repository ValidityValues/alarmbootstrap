# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.config
from pmb.helpers import logging

# Get magic and mask from binfmt info file
# Return: {magic: ..., mask: ...}


# FIXME: Maybe this should use Arch instead of str.
def binfmt_info(arch_qemu: str) -> dict[str, str]:
    # Parse the info file
    full = {}
    info = pmb.config.pmb_src / "pmb/data/qemu-user-binfmt.txt"
    logging.verbose(f"parsing: {info}")
    with open(info) as handle:
        for line in handle:
            if line.startswith("#") or "=" not in line:
                continue
            split = line.split("=")
            key = split[0].strip()
            value = split[1]
            full[key] = value[1:-2]

    ret = {}
    logging.verbose("filtering by architecture: " + arch_qemu)
    for type in ["mask", "magic"]:
        key = arch_qemu + "_" + type
        if key not in full:
            raise RuntimeError(f"Could not find key {key} in binfmt info file: {info}")
        ret[type] = full[key]
    logging.verbose("=> " + str(ret))
    return ret
