# Copyright 2026 Oliver Smith, Paul Adam
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pmb.aportgen.device
import pmb.parse
from pmb.helpers import logging


def bootimg_analyze(path: Path) -> None:
    bootimg = pmb.parse.bootimg(path)
    tmp_output = "Put these variables in the deviceinfo file of your device:\n"
    for line in pmb.aportgen.device.generate_deviceinfo_fastboot_content(bootimg).split("\n"):
        tmp_output += "\n" + line.lstrip()
    logging.info(tmp_output)
