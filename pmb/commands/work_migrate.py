# Copyright 2026 Hugo Posnic
# SPDX-License-Identifier: GPL-3.0-or-later
import pmb.helpers.logging


def work_migrate() -> None:
    # do nothing (pmb/__init__.py already did the migration)
    pmb.helpers.logging.disable()
