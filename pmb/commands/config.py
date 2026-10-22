# Copyright 2026 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from pathlib import Path

import pmb.config
from pmb.core import Config
from pmb.helpers import logging


def config(name: str | None, value: str | None, reset: bool, configpath: Path) -> None:
    keys = Config.keys()
    if name and name not in keys:
        logging.info("NOTE: Valid config keys: " + ", ".join(keys))
        raise RuntimeError("Invalid config key: " + name)

    # Reload the config because get_context().config has been overwritten
    # by any rogue cmdline arguments.
    config = pmb.config.load(configpath)
    if reset:
        if name is None:
            raise RuntimeError("config --reset requires a name to be given.")
        def_value = Config.get_default(name)
        setattr(config, name, def_value)
        logging.info(f"Config changed to default: {name}='{def_value}'")
        pmb.config.save(configpath, config)
    elif value is not None and name:
        if name.startswith("mirrors."):
            mirror = name.split(".", 1)[1]
            # Ignore mypy 'error: TypedDict name must be a string literal'.
            # Argparse already ensures 'mirror' is a valid Config.Mirrors key.
            if value_changed := (config.mirrors[mirror] != value):  # type: ignore[literal-required]
                config.mirrors[mirror] = value  # type: ignore[literal-required]
        elif isinstance(getattr(Config, name), list):
            new_list = value.split(",")
            if value_changed := (getattr(config, name, None) != new_list):
                setattr(config, name, new_list)
        else:
            if value_changed := (getattr(config, name) != value):
                setattr(config, name, value)
        if value_changed:
            print(f"{name} = {value}")
        pmb.config.save(configpath, config)
    elif name:
        to_print = getattr(config, name, "")
        if isinstance(to_print, list) and len(to_print) == 1:
            to_print = to_print[0]
        print(to_print.as_posix() if isinstance(to_print, Path) else str(to_print))
    else:
        # Serialize the entire config including default values for
        # the user. Even though the defaults aren't actually written
        # to disk.
        cfg = pmb.config.serialize(config, skip_defaults=False)
        cfg.write(sys.stdout)

    # Don't write the "Done" message
    logging.disable()
